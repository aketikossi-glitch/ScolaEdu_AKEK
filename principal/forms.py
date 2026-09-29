import random
import string
from django import forms
from django.contrib.auth.models import User
from core.models import Etablissement, ProfilUtilisateur


def generer_mot_de_passe(longueur=12):
    """Génère un mot de passe aléatoire sécurisé."""
    caracteres = string.ascii_letters + string.digits + "!@#$%&*"
    return ''.join(random.choice(caracteres) for _ in range(longueur))


# =====================================================
# CRÉATION ÉTABLISSEMENT + CHEF
# =====================================================
class CreerEtablissementForm(forms.Form):
    """Formulaire de création d'un établissement + son chef d'établissement."""

    # ===== ÉTABLISSEMENT =====
    nom = forms.CharField(
        max_length=200,
        label="Nom de l'établissement",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Collège d\'Enseignement Général d\'Agbavé'
        })
    )
    code = forms.CharField(
        max_length=20,
        label="Code unique",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: LOME001'
        })
    )
    type_etablissement = forms.ChoiceField(
        choices=Etablissement.TYPE_CHOICES,
        label="Type d'établissement",
        initial='complexe',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    ville = forms.CharField(
        max_length=100,
        initial='Lomé',
        label="Ville / Village / Commune",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    adresse = forms.CharField(
        max_length=255,
        required=False,
        label="Adresse",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    telephone = forms.CharField(
        max_length=20,
        required=False,
        label="Téléphone",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+228 90 00 00 00'})
    )
    # ✅ NOUVEAU : champ BP
    bp = forms.CharField(
        max_length=20,
        required=False,
        label="Boîte Postale (BP)",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1234'})
    )
    email = forms.EmailField(
        required=False,
        label="Email de l'établissement",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    numero_agrement = forms.CharField(
        max_length=50,
        required=False,
        label="N° d'agrément",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # ===== COMPTE DU CHEF =====
    chef_username = forms.CharField(
        max_length=150,
        label="Nom d'utilisateur du chef",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: chef_agbave'
        })
    )
    chef_first_name = forms.CharField(
        max_length=150,
        label="Prénom du chef",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    chef_last_name = forms.CharField(
        max_length=150,
        label="Nom du chef",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    chef_email = forms.EmailField(
        label="Email du chef",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    chef_telephone = forms.CharField(
        max_length=20,
        required=False,
        label="Téléphone du chef",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    chef_password = forms.CharField(
        max_length=128,
        required=False,
        label="Mot de passe",
        help_text="Laisser vide pour générer automatiquement",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Laisser vide = généré automatiquement'
        })
    )

    def clean_code(self):
        code = self.cleaned_data['code'].strip().upper()
        if Etablissement.objects.filter(code=code).exists():
            raise forms.ValidationError(f"Le code '{code}' est déjà utilisé.")
        return code

    def clean_chef_username(self):
        username = self.cleaned_data['chef_username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(f"Le nom d'utilisateur '{username}' est déjà pris.")
        return username

    def clean_chef_email(self):
        email = self.cleaned_data['chef_email'].strip().lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(f"L'email '{email}' est déjà utilisé.")
        return email

    def save(self):
        data = self.cleaned_data

        etablissement = Etablissement.objects.create(
            nom=data['nom'],
            code=data['code'],
            type_etablissement=data['type_etablissement'],
            ville=data['ville'],
            adresse=data.get('adresse', ''),
            telephone=data.get('telephone', ''),
            bp=data.get('bp', ''),  # ✅ NOUVEAU
            email=data.get('email', ''),
            numero_agrement=data.get('numero_agrement', ''),
            actif=True,
        )

        mot_de_passe = data.get('chef_password') or generer_mot_de_passe()

        chef = User.objects.create_user(
            username=data['chef_username'],
            email=data['chef_email'],
            password=mot_de_passe,
            first_name=data['chef_first_name'],
            last_name=data['chef_last_name'],
            is_staff=False,
            is_superuser=False,
        )

        ProfilUtilisateur.objects.create(
            user=chef,
            role='chef_etablissement',
            etablissement=etablissement,
            telephone=data.get('chef_telephone', ''),
        )

        return etablissement, chef, mot_de_passe


# =====================================================
# MODIFICATION ÉTABLISSEMENT
# =====================================================
class ModifierEtablissementForm(forms.ModelForm):
    """Modifier les informations d'un établissement."""

    class Meta:
        model = Etablissement
        # ✅ 'bp' AJOUTÉ dans fields
        fields = [
            'nom', 'code', 'type_etablissement', 'ville', 'adresse',
            'telephone', 'bp', 'email', 'numero_agrement', 'date_agrement', 'logo',
        ]
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'type_etablissement': forms.Select(attrs={'class': 'form-select'}),
            'ville': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.TextInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'bp': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1234'}),  # ✅ NOUVEAU
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'numero_agrement': forms.TextInput(attrs={'class': 'form-control'}),
            'date_agrement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'bp': "Boîte Postale (BP)",  # ✅ NOUVEAU
            'ville': "Ville / Village / Commune",
        }


# =====================================================
# AJOUT / MODIFICATION UTILISATEUR
# =====================================================
ROLES_AUTORISES = [
    ('chef_etablissement', "Chef d'établissement"),
    ('secretaire', 'Secrétaire'),
    ('comptable', 'Comptable'),
    ('enseignant', 'Enseignant'),
    ('surveillant', 'Surveillant'),
]


class AjouterUtilisateurForm(forms.Form):
    """Créer un utilisateur rattaché à un établissement."""

    username = forms.CharField(
        max_length=150,
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: mkoffi'
        })
    )
    first_name = forms.CharField(
        max_length=150,
        required=False,
        label="Prénom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label="Nom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=False,
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    telephone = forms.CharField(
        max_length=20,
        required=False,
        label="Téléphone",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=ROLES_AUTORISES,
        label="Rôle",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    password = forms.CharField(
        max_length=128,
        required=False,
        label="Mot de passe",
        help_text="Laisser vide pour générer automatiquement",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Laisser vide = généré automatiquement'
        })
    )
    specialite = forms.CharField(
        max_length=100,
        required=False,
        label="Spécialité",
        help_text="Pour les enseignants uniquement (ex: Mathématiques)",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.etablissement = kwargs.pop('etablissement', None)
        super().__init__(*args, **kwargs)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError(f"Le nom d'utilisateur '{username}' est déjà pris.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError(f"L'email '{email}' est déjà utilisé.")
        return email

    def save(self):
        from core.models import Enseignant
        data = self.cleaned_data
        mot_de_passe = data.get('password') or generer_mot_de_passe()

        user = User.objects.create_user(
            username=data['username'],
            email=data.get('email', ''),
            password=mot_de_passe,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
        )

        profil = ProfilUtilisateur.objects.create(
            user=user,
            role=data['role'],
            etablissement=self.etablissement,
            telephone=data.get('telephone', ''),
        )

        if data['role'] == 'enseignant':
            Enseignant.objects.create(
                user=user,
                etablissement=self.etablissement,
                specialite=data.get('specialite', ''),
                telephone=data.get('telephone', ''),
            )

        return user, mot_de_passe


class ModifierUtilisateurForm(forms.Form):
    """Modifier les informations d'un utilisateur."""

    first_name = forms.CharField(
        max_length=150,
        required=False,
        label="Prénom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        label="Nom",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=False,
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    telephone = forms.CharField(
        max_length=20,
        required=False,
        label="Téléphone",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role = forms.ChoiceField(
        choices=ROLES_AUTORISES,
        label="Rôle",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    specialite = forms.CharField(
        max_length=100,
        required=False,
        label="Spécialité",
        help_text="Pour les enseignants uniquement",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.profil = kwargs.pop('profil', None)
        super().__init__(*args, **kwargs)

        if self.profil:
            user = self.profil.user
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['email'].initial = user.email
            self.fields['telephone'].initial = self.profil.telephone
            self.fields['role'].initial = self.profil.role

            if self.profil.role == 'enseignant':
                try:
                    ens = user.enseignant
                    self.fields['specialite'].initial = ens.specialite
                except Exception:
                    pass

            if self.profil.role == 'chef_etablissement':
                self.fields['role'].disabled = True
                self.fields['role'].help_text = "Le rôle du chef ne peut pas être modifié."

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and self.profil:
            if User.objects.filter(email=email).exclude(pk=self.profil.user.pk).exists():
                raise forms.ValidationError(f"L'email '{email}' est déjà utilisé.")
        return email

    def save(self):
        from core.models import Enseignant
        data = self.cleaned_data
        user = self.profil.user

        user.first_name = data.get('first_name', '')
        user.last_name = data.get('last_name', '')
        user.email = data.get('email', '')
        user.save()

        if self.profil.role != 'chef_etablissement':
            self.profil.role = data['role']
        self.profil.telephone = data.get('telephone', '')
        self.profil.save()

        if self.profil.role == 'enseignant':
            ens, created = Enseignant.objects.get_or_create(
                user=user,
                defaults={
                    'etablissement': self.profil.etablissement,
                }
            )
            ens.specialite = data.get('specialite', '')
            ens.telephone = data.get('telephone', '')
            ens.save()

        return user


class ResetPasswordForm(forms.Form):
    """Formulaire pour réinitialiser le mot de passe d'un utilisateur."""

    nouveau_mot_de_passe = forms.CharField(
        max_length=128,
        required=False,
        label="Nouveau mot de passe",
        help_text="Laisser vide pour générer automatiquement",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Laisser vide = généré automatiquement'
        })
    )
