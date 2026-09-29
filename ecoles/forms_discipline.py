"""
ScolaEdu_AKEK — Formulaires du module Discipline (Session 18).
"""
from django import forms

from core.models import IncidentDisciplinaire, Sanction


# =====================================================
# INCIDENT DISCIPLINAIRE
# =====================================================
class IncidentForm(forms.ModelForm):
    """
    Formulaire d'incident avec sélection en 2 étapes :
      1. Choix de la classe (champ non persisté 'classe')
      2. Choix de l'élève (chargé dynamiquement via AJAX)
    """
    classe = forms.ChoiceField(
        label="Classe",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_classe'}),
    )

    class Meta:
        model = IncidentDisciplinaire
        fields = [
            'eleve', 'date_incident', 'heure_incident',
            'type_incident', 'gravite', 'description', 'statut',
        ]
        widgets = {
            'eleve': forms.Select(attrs={'class': 'form-select', 'id': 'id_eleve'}),
            'date_incident': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'heure_incident': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'type_incident': forms.Select(attrs={'class': 'form-select'}),
            'gravite': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Décrire brièvement les faits...'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'eleve': 'Élève concerné',
            'date_incident': "Date de l'incident",
            'heure_incident': "Heure (optionnel)",
            'type_incident': "Type d'incident",
            'gravite': 'Gravité',
            'description': 'Description',
            'statut': 'Statut du signalement',
        }

    def __init__(self, *args, **kwargs):
        etablissement = kwargs.pop('etablissement', None)
        eleve_initial = kwargs.pop('eleve_initial', None)
        classe_initial = kwargs.pop('classe_initial', None)
        super().__init__(*args, **kwargs)

        # Par défaut : aucune classe, aucun élève
        self.fields['classe'].choices = [('', '— Sélectionner une classe —')]
        self.fields['eleve'].choices = [('', '— Choisir d\'abord une classe —')]

        # Si un élève initial est passé : pré-sélectionner sa classe
        if eleve_initial is not None:
            self.fields['eleve'].choices = [
                ('', '— Choisir une classe —'),
                (eleve_initial.id, f"{eleve_initial.nom_complet} ({eleve_initial.matricule})"),
            ]
            self.fields['eleve'].initial = eleve_initial.id

        # Si on est en modification : passer l'élève courant
        if self.instance and self.instance.pk and self.instance.eleve_id:
            eleve = self.instance.eleve
            self.fields['eleve'].choices = [
                ('', '— Choisir une classe —'),
                (eleve.id, f"{eleve.nom_complet} ({eleve.matricule})"),
            ]
            self.fields['eleve'].initial = eleve.id

        # Remplir la liste des classes (si l'établissement est fourni)
        if etablissement is not None:
            from core.models import Classe, AnneeScolaire
            annee = AnneeScolaire.objects.filter(
                etablissement=etablissement, en_cours=True
            ).first()
            if annee:
                classes = Classe.objects.filter(
                    etablissement=etablissement, annee_scolaire=annee
                ).order_by('niveau', 'nom')
                self.fields['classe'].choices = [
                    ('', '— Sélectionner une classe —')
                ] + [
                    (c.id, f"{c.nom} ({c.get_niveau_display()})") for c in classes
                ]

            # Pré-sélection de la classe si demandée
            if classe_initial is not None:
                self.fields['classe'].initial = classe_initial

    def clean(self):
        cleaned = super().clean()
        eleve = cleaned.get('eleve')
        if not eleve:
            raise forms.ValidationError("Veuillez sélectionner un élève.")
        return cleaned


# =====================================================
# SANCTION
# =====================================================
class SanctionForm(forms.ModelForm):
    class Meta:
        model = Sanction
        fields = [
            'type_sanction', 'description',
            'date_debut', 'date_fin',
        ]
        widgets = {
            'type_sanction': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Détails de la sanction (optionnel)...'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'type_sanction': 'Type de sanction',
            'description': 'Description / détails',
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin (optionnel)',
        }

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('date_debut')
        fin = cleaned.get('date_fin')
        if debut and fin and debut > fin:
            raise forms.ValidationError("La date de fin doit être postérieure à la date de début.")
        return cleaned
