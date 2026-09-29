"""
ScolaEdu_AKEK — Formulaires du module Présences (Session 20).
"""
from django import forms
from datetime import date


# =====================================================
# SÉLECTION (classe + date)
# =====================================================
class SelectionPresenceForm(forms.Form):
    """Formulaire de sélection pour la saisie ou la consultation des présences."""

    classe = forms.ChoiceField(
        label="Classe",
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    date = forms.DateField(
        label="Date",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        initial=date.today,
    )

    def __init__(self, *args, **kwargs):
        classes = kwargs.pop('classes', [])
        super().__init__(*args, **kwargs)
        self.fields['classe'].choices = [
            ('', '— Sélectionner une classe —')
        ] + [
            (c.id, f"{c.nom} ({c.get_niveau_display()})") for c in classes
        ]
