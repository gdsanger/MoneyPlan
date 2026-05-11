"""Receipt recognition service using AI."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
import json
import io

from ai.service import complete_with_image
from ai.exceptions import AIServiceError, AIProviderNotConfigured, AIResponseParseError


@dataclass
class ReceiptRecognitionResult:
    """Result of AI receipt recognition."""
    date: Optional[str]              # "YYYY-MM-DD" or None
    description: str
    amount: Decimal
    category_suggestion: str         # suggested category name
    notes: str
    confidence: dict                 # {"date": "high", "amount": "high", "description": "medium"}
    raw_text: str
    ai_provider: str                 # which provider was used
    ai_model: str


def pdf_to_image(pdf_data: bytes) -> bytes:
    """
    Convert first page of PDF to JPEG image for vision models.

    Args:
        pdf_data: Raw PDF bytes

    Returns:
        JPEG image bytes

    Raises:
        ValueError: If PDF conversion fails
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        raise ValueError("pdf2image library not installed. Please install: pip install pdf2image")

    try:
        # Convert first page only at 200 DPI for good quality
        images = convert_from_bytes(pdf_data, first_page=1, last_page=1, dpi=200)

        if not images:
            raise ValueError("PDF contains no pages")

        # Convert PIL image to JPEG bytes
        img_byte_arr = io.BytesIO()
        images[0].save(img_byte_arr, format='JPEG', quality=95)
        img_byte_arr.seek(0)

        return img_byte_arr.getvalue()

    except Exception as e:
        raise ValueError(f"Failed to convert PDF to image: {str(e)}")


def recognize_receipt(file_data: bytes, mime_type: str) -> ReceiptRecognitionResult:
    """
    Sends receipt image/PDF to AI service and parses the structured response.

    For PDFs: converts first page to image before sending (using pdf2image / poppler).

    Args:
        file_data: Raw file bytes (image or PDF)
        mime_type: MIME type of the file

    Returns:
        ReceiptRecognitionResult with parsed data

    Raises:
        AIProviderNotConfigured: If AI service is not configured
        AIServiceError: If provider API call fails
        AIResponseParseError: If response is not valid JSON
        ValueError: If PDF conversion fails
    """
    # Convert PDF to image if needed
    if mime_type == 'application/pdf':
        image_data = pdf_to_image(file_data)
        image_mime_type = 'image/jpeg'
    else:
        image_data = file_data
        image_mime_type = mime_type

    # System prompt
    system_prompt = """Du bist ein Assistent zur Analyse von Belegen und Rechnungen für eine Finanzverwaltungs-App.
Extrahiere die relevanten Buchungsinformationen aus dem Beleg und antworte ausschließlich im folgenden JSON-Format, ohne zusätzlichen Text oder Markdown."""

    # User prompt
    user_prompt = """Analysiere diesen Beleg und extrahiere die Buchungsinformationen.

Antworte NUR mit einem JSON-Objekt in diesem Format:
{
  "date": "YYYY-MM-DD",
  "description": "Kurze prägnante Beschreibung (max. 60 Zeichen)",
  "amount": -29.50,
  "category_suggestion": "Telekommunikation",
  "notes": "Optionale Zusatzinformationen aus dem Beleg",
  "confidence": {
    "date": "high|medium|low",
    "amount": "high|medium|low",
    "description": "high|medium|low"
  },
  "raw_text": "Relevanter extrahierter Text aus dem Beleg (max. 200 Zeichen)"
}

Regeln:
- amount: negativ für Ausgaben, positiv für Einnahmen/Gutschriften
- date: Rechnungsdatum oder Leistungsdatum, falls kein Datum erkennbar: null
- category_suggestion: eine der folgenden Kategorien wählen oder "Sonstiges":
  Gehalt, Miete, Lebensmittel, Transport, Versicherungen, Telekommunikation,
  Gesundheit, Freizeit, Bildung, Sonstiges
- confidence: "high" wenn eindeutig erkennbar, "low" wenn geschätzt oder unklar"""

    # Call AI service
    try:
        response = complete_with_image(
            image_data=image_data,
            image_mime_type=image_mime_type,
            prompt=user_prompt,
            system_prompt=system_prompt,
            feature="receipt_recognition",
            max_tokens=1000,
        )
    except AIProviderNotConfigured:
        raise
    except Exception as e:
        raise AIServiceError(f"AI provider failed: {str(e)}")

    # Parse JSON response
    try:
        # Try to extract JSON from response (handle markdown code blocks)
        content = response.content.strip()

        # Remove markdown code fences if present
        if content.startswith('```'):
            # Find first newline after opening fence
            start = content.find('\n')
            # Find closing fence
            end = content.rfind('```')
            if start != -1 and end != -1:
                content = content[start+1:end].strip()

        data = json.loads(content)

        # Validate required fields
        required_fields = ['date', 'description', 'amount', 'category_suggestion', 'confidence', 'raw_text']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            raise AIResponseParseError(f"Missing required fields in AI response: {', '.join(missing_fields)}")

        # Build result
        result = ReceiptRecognitionResult(
            date=data['date'],  # Can be None
            description=data['description'],
            amount=Decimal(str(data['amount'])),
            category_suggestion=data['category_suggestion'],
            notes=data.get('notes', ''),
            confidence=data['confidence'],
            raw_text=data['raw_text'],
            ai_provider=response.provider,
            ai_model=response.model,
        )

        return result

    except json.JSONDecodeError as e:
        raise AIResponseParseError(f"Invalid JSON in AI response: {str(e)}")
    except (KeyError, ValueError, TypeError) as e:
        raise AIResponseParseError(f"Failed to parse AI response: {str(e)}")
