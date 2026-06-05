from django.db import migrations


CATEGORY_DATA = {
    'Gehalt': {
        'category_type': 'income',
        'description': 'Regelmäßiges Einkommen aus unselbständiger oder selbständiger Arbeit.',
    },
    'Miete': {
        'category_type': 'expense',
        'description': 'Wohnkosten inkl. Miete, Nebenkosten und Hausgeld.',
    },
    'Lebensmittel': {
        'category_type': 'expense',
        'description': 'Einkäufe für Lebensmittel und Getränke im Supermarkt oder online.',
    },
    'Transport': {
        'category_type': 'expense',
        'description': 'ÖPNV, Benzin, Parkgebühren, Fahrzeugkosten und Mobilität.',
    },
    'Versicherungen': {
        'category_type': 'expense',
        'description': 'Versicherungsbeiträge wie Haftpflicht, Hausrat, Kfz oder Berufsunfähigkeit.',
    },
    'Telekommunikation': {
        'category_type': 'expense',
        'description': 'Mobilfunk, Internet, Festnetz und verwandte Telekommunikationskosten.',
    },
    'Gesundheit': {
        'category_type': 'expense',
        'description': 'Arzt, Apotheke, Medikamente und Gesundheitsausgaben.',
    },
    'Freizeit': {
        'category_type': 'expense',
        'description': 'Unterhaltung, Hobbys, Reisen, Restaurants und Freizeitaktivitäten.',
    },
    'Bildung': {
        'category_type': 'expense',
        'description': 'Kurse, Bücher, Weiterbildung und Bildungsausgaben.',
    },
    'Sonstiges': {
        'category_type': 'expense',
        'description': 'Ausgaben, die keiner spezifischen Kategorie zugeordnet werden können.',
    },
}

NEUTRAL_CATEGORY = {
    'name': 'Neutral',
    'icon': 'bi-arrow-left-right',
    'color': '#adb5bd',
    'category_type': 'neutral',
    'description': 'Durchlaufende Posten, Umbuchungen zwischen Konten und interne Transfers ohne Einnahmen- oder Ausgabenwirkung.',
}


def populate_category_types(apps, schema_editor):
    Category = apps.get_model('bookings', 'Category')

    for name, data in CATEGORY_DATA.items():
        Category.objects.filter(name=name).update(**data)

    if not Category.objects.filter(name=NEUTRAL_CATEGORY['name']).exists():
        Category.objects.create(**NEUTRAL_CATEGORY)


def reverse_populate(apps, schema_editor):
    Category = apps.get_model('bookings', 'Category')
    Category.objects.filter(name=NEUTRAL_CATEGORY['name']).delete()
    Category.objects.all().update(category_type='expense', description='')


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0006_add_category_type_and_description'),
    ]

    operations = [
        migrations.RunPython(populate_category_types, reverse_populate),
    ]
