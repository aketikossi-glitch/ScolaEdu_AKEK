from django import forms
from django.db import models
from core.models import (
    AnneeScolaire, Classe, Matiere, MatiereClasse, Enseignant,
    Eleve, Inscription, Trimestre
)


# =====================================================
# ANNÉE SCOLAIRE
# =====================================================
class AnneeScolaireForm(forms.ModelForm):
    class Meta:
        model = AnneeScolaire
        fields = ['libelle', 'date_debut', 'date_fin', 'en_cours']
        widgets = {
            'libelle': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 2025-2026', 'maxlength': '9'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'en_cours': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'libelle': "Libellé de l'année",
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin',
            'en_cours': "Activer immédiatement cette année",
        }

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('date_debut')
        fin = cleaned.get('date_fin')
        if debut and fin and debut >= fin:
            raise forms.ValidationError("La date de fin doit être postérieure à la date de début.")
        return cleaned


# =====================================================
# TRIMESTRES
# =====================================================
class TrimestresForm(forms.Form):
    DUREE_CHOICES = [(i, f"{i} mois") for i in range(1, 7)]
    duree_trimestre1 = forms.ChoiceField(label="Durée du 1er trimestre", choices=DUREE_CHOICES, initial=3, widget=forms.Select(attrs={'class': 'form-select'}))
    duree_trimestre2 = forms.ChoiceField(label="Durée du 2ème trimestre", choices=DUREE_CHOICES, initial=3, widget=forms.Select(attrs={'class': 'form-select'}))
    duree_trimestre3 = forms.ChoiceField(label="Durée du 3ème trimestre", choices=DUREE_CHOICES, initial=3, widget=forms.Select(attrs={'class': 'form-select'}))
    pause_jours = forms.IntegerField(label="Pause entre les trimestres (jours)", initial=15, min_value=0, max_value=60, widget=forms.NumberInput(attrs={'class': 'form-control'}))


# =====================================================
# CONFIGURATION ÉTABLISSEMENT
# =====================================================
class ConfigurationEtablissementForm(forms.ModelForm):
    class Meta:
        from core.models import ConfigurationEtablissement
        model = ConfigurationEtablissement
        fields = [
            'pays', 'devise_nationale', 'ministere', 'direction_regionale',
            'inspection', 'prefecture', 'commune', 'perimetre_pedagogique', 'commune_administration',
            'nom_officiel', 'devise_ecole', 'mode_en_tete', 'en_tete_image',
            'nom_chef', 'titre_chef', 'signature_chef', 'cachet_ecole',
            'annee_fondation', 'autorisation_ouverture', 'sceau_ministere',
            'pied_de_page', 'ville_document',
            'note_passage',
        ]
        widgets = {
            'pays': forms.TextInput(attrs={'class': 'form-control'}),
            'devise_nationale': forms.TextInput(attrs={'class': 'form-control'}),
            'ministere': forms.TextInput(attrs={'class': 'form-control'}),
            'direction_regionale': forms.TextInput(attrs={'class': 'form-control'}),
            'inspection': forms.TextInput(attrs={'class': 'form-control'}),
            'prefecture': forms.TextInput(attrs={'class': 'form-control'}),
            'commune': forms.TextInput(attrs={'class': 'form-control'}),
            'perimetre_pedagogique': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: HAHO'}),
            'commune_administration': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Akpakpakpe'}),
            'nom_officiel': forms.TextInput(attrs={'class': 'form-control'}),
            'devise_ecole': forms.TextInput(attrs={'class': 'form-control'}),
            'mode_en_tete': forms.Select(attrs={'class': 'form-select'}),
            'en_tete_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'nom_chef': forms.TextInput(attrs={'class': 'form-control'}),
            'titre_chef': forms.TextInput(attrs={'class': 'form-control'}),
            'signature_chef': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'cachet_ecole': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'annee_fondation': forms.TextInput(attrs={'class': 'form-control'}),
            'autorisation_ouverture': forms.TextInput(attrs={'class': 'form-control'}),
            'sceau_ministere': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'pied_de_page': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ville_document': forms.TextInput(attrs={'class': 'form-control'}),
            'note_passage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '20', 'step': '0.25'}),
        }
        labels = {
            'commune': "Ville / Village / Commune",  # ✅ Renommé de "Commune" à "Ville"
            'note_passage': "Note de passage (sur 20)",
            'perimetre_pedagogique': "Périmètre pédagogique",
            'commune_administration': "Commune administrative",
        }
        help_texts = {
            'commune': "La ville utilisée dans le 'Fait à ...' des bulletins.",
            'note_passage': "Moyenne minimale pour passer en classe supérieure (par défaut : 10/20).",
        }


# =====================================================
# CLASSES
# =====================================================
class ClasseForm(forms.ModelForm):
    class Meta:
        model = Classe
        fields = ['nom', 'niveau', 'effectif_max', 'titulaire']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 6ème A', 'maxlength': '50'}),
            'niveau': forms.Select(attrs={'class': 'form-select'}),
            'effectif_max': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '200'}),
            'titulaire': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nom': 'Nom de la classe',
            'niveau': 'Niveau',
            'effectif_max': 'Capacité maximale',
            'titulaire': 'Professeur titulaire (optionnel)',
        }
        help_texts = {
            'titulaire': "Le professeur principal de cette classe.",
        }

    def __init__(self, *args, **kwargs):
        self.etablissement = kwargs.pop('etablissement', None)
        self.annee_scolaire = kwargs.pop('annee_scolaire', None)
        super().__init__(*args, **kwargs)

        if self.etablissement:
            self.fields['titulaire'].queryset = Enseignant.objects.filter(
                etablissement=self.etablissement
            ).order_by('user__last_name', 'user__first_name')
            self.fields['titulaire'].required = False

    def clean_nom(self):
        nom = self.cleaned_data['nom'].strip()
        if self.etablissement and self.annee_scolaire:
            qs = Classe.objects.filter(etablissement=self.etablissement, annee_scolaire=self.annee_scolaire, nom__iexact=nom)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Une classe nommée '{nom}' existe déjà.")
        return nom


# =====================================================
# MATIÈRES
# =====================================================
class MatiereForm(forms.ModelForm):
    class Meta:
        model = Matiere
        fields = ['nom', 'code', 'coefficient', 'ordre', 'description']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Mathématiques'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: MATH'}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'ordre': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '999'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'nom': 'Nom de la matière',
            'code': 'Code (unique)',
            'coefficient': 'Coefficient par défaut',
            'ordre': "Ordre d'affichage",
            'description': 'Description (optionnel)',
        }
        help_texts = {
            'code': "Un code court et unique (ex: MATH, FR, ANG)",
            'coefficient': "De 1 à 10",
            'ordre': "1 = en haut de la liste",
        }

    def __init__(self, *args, **kwargs):
        self.etablissement = kwargs.pop('etablissement', None)
        self.annee_scolaire = kwargs.pop('annee_scolaire', None)
        super().__init__(*args, **kwargs)

    def clean_nom(self):
        nom = self.cleaned_data['nom'].strip()
        if self.etablissement and self.annee_scolaire:
            qs = Matiere.objects.filter(etablissement=self.etablissement, annee_scolaire=self.annee_scolaire, nom__iexact=nom)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Une matière nommée '{nom}' existe déjà.")
        return nom

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if self.etablissement and self.annee_scolaire:
            qs = Matiere.objects.filter(etablissement=self.etablissement, annee_scolaire=self.annee_scolaire, code__iexact=code)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Le code '{code}' est déjà utilisé.")
        return code

    def clean_ordre(self):
        ordre = self.cleaned_data['ordre']
        if self.etablissement and self.annee_scolaire:
            qs = Matiere.objects.filter(etablissement=self.etablissement, annee_scolaire=self.annee_scolaire, ordre=ordre)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"L'ordre {ordre} est déjà utilisé.")
        return ordre


# =====================================================
# CHOIX ENSEIGNANT (avec spécialité affichée)
# =====================================================
class EnseignantChoiceField(forms.ModelChoiceField):
    """ModelChoiceField qui affiche 'Nom Prénom — Spécialité'."""
    def label_from_instance(self, obj):
        nom = obj.user.get_full_name() or obj.user.username
        if obj.specialite:
            return f"{nom} — {obj.specialite}"
        return nom


# =====================================================
# MATIÈRES PAR CLASSE
# =====================================================
class MatiereClasseForm(forms.ModelForm):
    class Meta:
        model = MatiereClasse
        fields = ['matiere', 'coefficient', 'enseignant']
        widgets = {
            'matiere': forms.Select(attrs={'class': 'form-select'}),
            'coefficient': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'enseignant': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'matiere': 'Matière',
            'coefficient': 'Coefficient pour cette classe',
            'enseignant': "Enseignant (optionnel)",
        }

    def __init__(self, *args, **kwargs):
        self.classe = kwargs.pop('classe', None)
        self.etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)

        if self.classe and self.etablissement:
            annee = self.classe.annee_scolaire
            matieres = Matiere.objects.filter(etablissement=self.etablissement, annee_scolaire=annee).order_by('ordre', 'nom')
            deja_affectees = MatiereClasse.objects.filter(classe=self.classe).values_list('matiere_id', flat=True)
            if self.instance and self.instance.pk:
                matieres = matieres.filter(models.Q(id=self.instance.matiere_id) | ~models.Q(id__in=deja_affectees))
            else:
                matieres = matieres.exclude(id__in=deja_affectees)
            self.fields['matiere'].queryset = matieres
            # ✅ Choix enseignant avec spécialité affichée
            self.fields['enseignant'] = EnseignantChoiceField(
                queryset=Enseignant.objects.filter(
                    etablissement=self.etablissement
                ).order_by('user__last_name', 'user__first_name'),
                required=False,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label="Enseignant (optionnel)",
            )

    def clean_coefficient(self):
        coef = self.cleaned_data['coefficient']
        if coef < 1 or coef > 10:
            raise forms.ValidationError("Le coefficient doit être entre 1 et 10.")
        return coef


class AffectationEnMasseForm(forms.Form):
    matieres = forms.ModelMultipleChoiceField(queryset=Matiere.objects.none(), widget=forms.CheckboxSelectMultiple(), label="Matières à affecter")

    def __init__(self, *args, **kwargs):
        self.classe = kwargs.pop('classe', None)
        self.etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)
        if self.classe and self.etablissement:
            annee = self.classe.annee_scolaire
            matieres = Matiere.objects.filter(etablissement=self.etablissement, annee_scolaire=annee).order_by('ordre', 'nom')
            deja_affectees = MatiereClasse.objects.filter(classe=self.classe).values_list('matiere_id', flat=True)
            self.fields['matieres'].queryset = matieres.exclude(id__in=deja_affectees)


# =====================================================
# ÉLÈVE
# =====================================================
class EleveForm(forms.ModelForm):
    class Meta:
        model = Eleve
        fields = [
            'matricule', 'nom', 'prenom', 'sexe', 'date_naissance', 'lieu_naissance', 'prefecture_naissance', 'nationalite', 'statut',
            'nom_pere', 'telephone_pere', 'profession_pere', 'adresse_pere', 'email_pere',
            'nom_mere', 'telephone_mere', 'profession_mere', 'adresse_mere', 'email_mere',
            'nom_tuteur', 'telephone_tuteur', 'profession_tuteur', 'adresse_tuteur', 'email_tuteur',
            'adresse', 'photo',
        ]
        widgets = {
            'matricule': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'sexe': forms.Select(attrs={'class': 'form-select'}),
            'date_naissance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'lieu_naissance': forms.TextInput(attrs={'class': 'form-control'}),
            'prefecture_naissance': forms.Select(attrs={'class': 'form-select'}),
            'nationalite': forms.TextInput(attrs={'class': 'form-control'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'nom_pere': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_pere': forms.TextInput(attrs={'class': 'form-control'}),
            'profession_pere': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse_pere': forms.TextInput(attrs={'class': 'form-control'}),
            'email_pere': forms.EmailInput(attrs={'class': 'form-control'}),
            'nom_mere': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_mere': forms.TextInput(attrs={'class': 'form-control'}),
            'profession_mere': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse_mere': forms.TextInput(attrs={'class': 'form-control'}),
            'email_mere': forms.EmailInput(attrs={'class': 'form-control'}),
            'nom_tuteur': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone_tuteur': forms.TextInput(attrs={'class': 'form-control'}),
            'profession_tuteur': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse_tuteur': forms.TextInput(attrs={'class': 'form-control'}),
            'email_tuteur': forms.EmailInput(attrs={'class': 'form-control'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def __init__(self, *args, **kwargs):
        self.etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)

    def clean_matricule(self):
        matricule = self.cleaned_data['matricule'].strip()
        if self.etablissement:
            qs = Eleve.objects.filter(etablissement=self.etablissement, matricule=matricule)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"Le matricule '{matricule}' est déjà utilisé.")
        return matricule

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo and hasattr(photo, 'file'):
            try:
                from core.utils import traiter_photo_passeport
                resultat = traiter_photo_passeport(photo)
                if resultat:
                    return resultat
                return photo
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Erreur clean_photo: {e}")
                return photo
        if self.instance and self.instance.pk and self.instance.photo:
            return self.instance.photo
        return photo


# =====================================================
# INSCRIPTION
# =====================================================
class InscriptionForm(forms.Form):
    classe = forms.ModelChoiceField(queryset=Classe.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}), label="Classe")

    def __init__(self, *args, **kwargs):
        self.eleve = kwargs.pop('eleve', None)
        self.etablissement = kwargs.pop('etablissement', None)
        self.annee_scolaire = kwargs.pop('annee_scolaire', None)
        super().__init__(*args, **kwargs)

        if self.etablissement and self.annee_scolaire:
            self.fields['classe'].queryset = Classe.objects.filter(
                etablissement=self.etablissement,
                annee_scolaire=self.annee_scolaire
            ).order_by('niveau', 'nom')

    def clean_classe(self):
        classe = self.cleaned_data['classe']
        nb_inscrits = Inscription.objects.filter(classe=classe, actif=True).count()
        if nb_inscrits >= classe.effectif_max:
            raise forms.ValidationError(f"La classe '{classe.nom}' est pleine ({nb_inscrits}/{classe.effectif_max}).")
        if self.eleve and self.annee_scolaire:
            if Inscription.objects.filter(eleve=self.eleve, annee_scolaire=self.annee_scolaire, actif=True).exists():
                raise forms.ValidationError(f"L'élève est déjà inscrit pour l'année {self.annee_scolaire.libelle}.")
        return classe


# =====================================================
# NOTES
# =====================================================
class SelectionNotesForm(forms.Form):
    classe = forms.ModelChoiceField(queryset=Classe.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}), label="Classe")
    matiere = forms.ModelChoiceField(queryset=Matiere.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}), label="Matière")
    trimestre = forms.ModelChoiceField(queryset=Trimestre.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}), label="Trimestre")

    def __init__(self, *args, **kwargs):
        self.etablissement = kwargs.pop('etablissement', None)
        self.annee_scolaire = kwargs.pop('annee_scolaire', None)
        super().__init__(*args, **kwargs)

        if self.etablissement and self.annee_scolaire:
            self.fields['classe'].queryset = Classe.objects.filter(
                etablissement=self.etablissement,
                annee_scolaire=self.annee_scolaire,
            ).order_by('niveau', 'nom')

            self.fields['matiere'].queryset = Matiere.objects.filter(
                etablissement=self.etablissement,
                annee_scolaire=self.annee_scolaire,
            ).order_by('ordre', 'nom')

            self.fields['trimestre'].queryset = Trimestre.objects.filter(
                etablissement=self.etablissement,
                annee_scolaire=self.annee_scolaire.libelle,
            ).order_by('numero')


class NotesForm(forms.Form):
    note_devoir1 = forms.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=20, required=False, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm note-input', 'step': '0.25', 'min': '0', 'max': '20', 'placeholder': '0-20'}))
    note_devoir2 = forms.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=20, required=False, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm note-input', 'step': '0.25', 'min': '0', 'max': '20', 'placeholder': '0-20'}))
    note_composition = forms.DecimalField(max_digits=4, decimal_places=2, min_value=0, max_value=20, required=False, widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm note-input', 'step': '0.25', 'min': '0', 'max': '20', 'placeholder': '0-20'}))

    def clean_note_devoir1(self):
        val = self.cleaned_data.get('note_devoir1')
        if val is not None and (val < 0 or val > 20):
            raise forms.ValidationError("La note doit être entre 0 et 20.")
        return val

    def clean_note_devoir2(self):
        val = self.cleaned_data.get('note_devoir2')
        if val is not None and (val < 0 or val > 20):
            raise forms.ValidationError("La note doit être entre 0 et 20.")
        return val

    def clean_note_composition(self):
        val = self.cleaned_data.get('note_composition')
        if val is not None and (val < 0 or val > 20):
            raise forms.ValidationError("La note doit être entre 0 et 20.")
        return val
