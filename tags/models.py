from django.db import models


class Tag(models.Model):
    """Frei vergebbares Schlagwort mit Dimension, z.B. für Projekte, Kunden oder Kostenstellen."""

    KIND_CHOICES = [
        ('projekt', 'Projekt'),
        ('kunde', 'Kunde'),
        ('kostenstelle', 'Kostenstelle'),
        ('sonstiges', 'Sonstiges'),
    ]

    name = models.CharField(max_length=100, verbose_name="Name")
    kind = models.CharField(
        max_length=20,
        choices=KIND_CHOICES,
        default='sonstiges',
        verbose_name="Dimension",
    )
    color = models.CharField(max_length=7, default="#6c757d", verbose_name="Farbe (Hex)")
    description = models.TextField(blank=True, max_length=500, verbose_name="Beschreibung")
    archived = models.BooleanField(default=False, verbose_name="Archiviert")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Erstellt am")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ['kind', 'name']
        constraints = [
            models.UniqueConstraint(fields=['kind', 'name'], name='unique_tag_kind_name'),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"

    @classmethod
    def grouped_choices(cls, queryset=None):
        """Choices für Select-Felder, gruppiert nach Dimension (kind) als optgroups."""
        qs = cls.objects.filter(archived=False) if queryset is None else queryset
        kind_labels = dict(cls.KIND_CHOICES)
        groups = []
        current_kind = object()
        for tag in qs.order_by('kind', 'name'):
            if tag.kind != current_kind:
                current_kind = tag.kind
                groups.append((kind_labels.get(tag.kind, tag.kind), []))
            groups[-1][1].append((tag.pk, tag.name))
        return groups
