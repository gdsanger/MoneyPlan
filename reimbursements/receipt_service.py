"""Fuel receipt recognition using AI."""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
import json

from ai.service import complete_with_image
from ai.exceptions import AIServiceError, AIProviderNotConfigured, AIResponseParseError
from bookings.receipt_service import pdf_to_image


@dataclass
class FuelReceiptResult:
    date: Optional[str]
    description: str
    amount: Decimal
    notes: str
    confidence: dict
    raw_text: str
    ai_provider: str
    ai_model: str


def recognize_fuel_receipt(file_data: bytes, mime_type: str) -> FuelReceiptResult:
    """Analyze a fuel receipt image/PDF and extract structured data."""
    if mime_type == 'application/pdf':
        image_data = pdf_to_image(file_data)
        image_mime_type = 'image/jpeg'
    else:
        image_data = file_data
        image_mime_type = mime_type

    system_prompt = (
        'Du bist ein Assistent zur Analyse von Tankbelegen für eine Auslagenerstattung. '
        'Extrahiere die relevanten Informationen und antworte ausschließlich im JSON-Format.'
    )

    user_prompt = """Analysiere diesen Tankbeleg und extrahiere die Informationen.

Antworte NUR mit einem JSON-Objekt in diesem Format:
{
  "date": "YYYY-MM-DD",
  "description": "Tankstelle oder kurze Beschreibung (max. 60 Zeichen)",
  "amount": 101.07,
  "notes": "Optionale Zusatzinfos (Liter, Kraftstoffart, KM)",
  "confidence": {
    "date": "high|medium|low",
    "amount": "high|medium|low",
    "description": "high|medium|low"
  },
  "raw_text": "Relevanter extrahierter Text (max. 200 Zeichen)"
}

Regeln:
- amount: positiver Bruttobetrag in Euro (nur Zahl, ohne Währungssymbol)
- date: Tankdatum; null wenn nicht erkennbar
- description: Name der Tankstelle oder „Tanken“ falls unklar"""

    try:
        response = complete_with_image(
            image_data=image_data,
            image_mime_type=image_mime_type,
            prompt=user_prompt,
            system_prompt=system_prompt,
            feature='fuel_receipt_recognition',
            max_tokens=1000,
        )
    except AIProviderNotConfigured:
        raise
    except Exception as e:
        raise AIServiceError(f'AI provider failed: {str(e)}')

    try:
        content = response.content.strip()
        if content.startswith('```'):
            start = content.find('\n')
            end = content.rfind('```')
            if start != -1 and end != -1:
                content = content[start + 1:end].strip()

        data = json.loads(content)
        required_fields = ['date', 'description', 'amount', 'confidence', 'raw_text']
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise AIResponseParseError(f'Missing required fields: {", ".join(missing)}')

        amount = Decimal(str(data['amount']))
        if amount < 0:
            amount = abs(amount)

        return FuelReceiptResult(
            date=data['date'],
            description=data['description'],
            amount=amount,
            notes=data.get('notes', ''),
            confidence=data['confidence'],
            raw_text=data['raw_text'],
            ai_provider=response.provider,
            ai_model=response.model,
        )
    except json.JSONDecodeError as e:
        raise AIResponseParseError(f'Invalid JSON in AI response: {str(e)}')
    except (KeyError, ValueError, TypeError) as e:
        raise AIResponseParseError(f'Failed to parse AI response: {str(e)}')
