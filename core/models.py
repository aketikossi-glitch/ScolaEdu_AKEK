from django.db import models
from django.contrib.auth.models import User


# =====================================================
# ÉTABLISSEMENT & UTILISATEURS
# =====================================================

class Etablissement(models.Model):
    TYPE_CHOICES = [
        ('maternelle', 'Maternelle'),
        ('primaire', 'Primaire'),
        ('college', 'Collège'),
        ('lycee', 'Lycée'),
        ('complexe', 'Complexe scolaire'),
    ]

    nom = models.CharField(max_length=200, verbose_name="Nom de l'établissement")
    type_etablissement = models.CharField(max_length=20, choices=TYPE_CHOICES, default='complexe')
    code = models.CharField(max_length=20, unique=True)
    adresse = models.CharField(max_length=255, blank=True)
    ville = models.CharField(max_length=100, default='Lomé')
    telephone = models.CharField(max_length=20, blank=True)
    bp = models.CharField(max_length=20, blank=True, verbose_name="Boîte Postale")  # ✅ AJOUTÉ
    email = models.EmailField(blank=True)
    numero_agrement = models.CharField(max_length=50, blank=True)
    date_agrement = models.DateField(null=True, blank=True)
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    actif = models.BooleanField(default=True)
    raison_suspension = models.TextField(blank=True)
    date_suspension = models.DateTimeField(null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.code})"

    def est_vide(self):
        from django.apps import apps
        try:
            AnneeScolaire = apps.get_model('core', 'AnneeScolaire')
            Classe = apps.get_model('core', 'Classe')
            Eleve = apps.get_model('core', 'Eleve')
            Enseignant = apps.get_model('core', 'Enseignant')
            Note = apps.get_model('core', 'Note')
            if AnneeScolaire.objects.filter(etablissement=self).exists():
                return False
            if Classe.objects.filter(etablissement=self).exists():
                return False
            if Eleve.objects.filter(etablissement=self).exists():
                return False
            if Enseignant.objects.filter(etablissement=self).exists():
                return False
            if Note.objects.filter(eleve__etablissement=self).exists():
                return False
            return True
        except Exception:
            return False


class ProfilUtilisateur(models.Model):
    ROLE_CHOICES = [
        ('admin_principal', 'Admin Principal'),
        ('chef_etablissement', "Chef d'établissement"),
        ('secretaire', 'Secrétaire'),
        ('comptable', 'Comptable'),
        ('enseignant', 'Enseignant'),
        ('surveillant', 'Surveillant'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, null=True, blank=True, related_name='personnels')
    telephone = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        nom_complet = self.user.get_full_name() or self.user.username
        return f"{nom_complet} — {self.get_role_display()}"

    def est_gestionnaire(self):
        return self.role in ('admin_principal', 'chef_etablissement', 'secretaire')

    def est_chef_ou_admin(self):
        return self.role in ('admin_principal', 'chef_etablissement')


# =====================================================
# ANNÉE SCOLAIRE
# =====================================================

class AnneeScolaire(models.Model):
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='annees_scolaires')
    libelle = models.CharField(max_length=9)
    date_debut = models.DateField()
    date_fin = models.DateField()
    en_cours = models.BooleanField(default=False)
    cloturee = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Année scolaire"
        verbose_name_plural = "Années scolaires"
        unique_together = ('etablissement', 'libelle')
        ordering = ['-libelle']

    def __str__(self):
        return f"{self.libelle} — {self.etablissement.nom}"

    def save(self, *args, **kwargs):
        if self.en_cours:
            AnneeScolaire.objects.filter(etablissement=self.etablissement, en_cours=True).exclude(pk=self.pk).update(en_cours=False, cloturee=True)
            self.cloturee = False
        super().save(*args, **kwargs)


# =====================================================
# MATIÈRES
# =====================================================

class Matiere(models.Model):
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='matieres')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='matieres', null=True, blank=True)
    nom = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    coefficient = models.PositiveIntegerField(default=1)
    ordre = models.PositiveIntegerField(default=100)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Matière"
        verbose_name_plural = "Matières"
        ordering = ['ordre', 'nom']
        unique_together = ('etablissement', 'annee_scolaire', 'code')

    def __str__(self):
        return f"{self.nom} (coef. {self.coefficient})"


# =====================================================
# CLASSES
# =====================================================

class Classe(models.Model):
    NIVEAU_CHOICES = [
        ('maternelle', 'Maternelle'),
        ('cp1', 'CP1'), ('cp2', 'CP2'),
        ('ce1', 'CE1'), ('ce2', 'CE2'),
        ('cm1', 'CM1'), ('cm2', 'CM2'),
        ('6eme', '6ème'), ('5eme', '5ème'),
        ('4eme', '4ème'), ('3eme', '3ème'),
        ('2nde', '2nde'), ('1ere', '1ère'),
        ('tle', 'Terminale'),
    ]

    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='classes')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='classes', null=True, blank=True)
    nom = models.CharField(max_length=50)
    niveau = models.CharField(max_length=20, choices=NIVEAU_CHOICES)
    effectif_max = models.PositiveIntegerField(default=60)

    # ⭐ NOUVEAU : Titulaire de classe (professeur principal)
    titulaire = models.ForeignKey(
        'Enseignant',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='classes_titulaire',
        verbose_name="Professeur titulaire",
    )

    class Meta:
        verbose_name = "Classe"
        verbose_name_plural = "Classes"
        ordering = ['niveau', 'nom']

    def __str__(self):
        annee = self.annee_scolaire.libelle if self.annee_scolaire else "?"
        return f"{self.nom} ({annee})"

    @property
    def est_classe_examen(self):
        """Retourne True si la classe est une classe d'examen (CEPD/BEPC/BAC1/BAC2)."""
        return self.niveau in ('cm2', '3eme', '1ere', 'tle')

    @property
    def titre_examen(self):
        """Retourne le nom de l'examen associé à ce niveau."""
        return {
            'cm2': 'CEPD',
            '3eme': 'BEPC',
            '1ere': 'BAC1',
            'tle': 'BAC2',
        }.get(self.niveau, '')


# =====================================================
# ENSEIGNANTS
# =====================================================

class Enseignant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='enseignant')
    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='enseignants')
    matricule = models.CharField(max_length=30, blank=True)
    specialite = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=20, blank=True)
    date_embauche = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Enseignant"
        verbose_name_plural = "Enseignants"
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}"


class MatiereClasse(models.Model):
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='matieres')
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='classes')
    coefficient = models.PositiveIntegerField(default=1)
    enseignant = models.ForeignKey(Enseignant, on_delete=models.SET_NULL, null=True, blank=True, related_name='matieres_enseignees')

    class Meta:
        verbose_name = "Matière par classe"
        verbose_name_plural = "Matières par classe"
        unique_together = ('classe', 'matiere')

    def __str__(self):
        return f"{self.classe.nom} — {self.matiere.nom}"


# =====================================================
# ÉLÈVES & INSCRIPTIONS
# =====================================================

class Eleve(models.Model):
    SEXE_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]
    STATUT_CHOICES = [
        ('nouveau', 'Nouveau'),
        ('redoublant', 'Redoublant'),
        ('transfere', 'Transféré'),
    ]

    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='eleves')
    matricule = models.CharField(max_length=30)

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES)
    date_naissance = models.DateField()
    lieu_naissance = models.CharField(max_length=100, blank=True)
    prefecture_naissance = models.CharField(
        max_length=100, blank=True,
        verbose_name="Préfecture de naissance",
        choices=[
            # =====================================================
            # RÉGION MARITIME (8 préfectures)
            # =====================================================
            ('Maritime|Avé', 'Avé'),
            ('Maritime|Bas-Mono', 'Bas-Mono'),
            ('Maritime|Golfe', 'Golfe'),
            ('Maritime|Lacs', 'Lacs'),
            ('Maritime|Vo', 'Vo'),
            ('Maritime|Yoto', 'Yoto'),
            ('Maritime|Zio', 'Zio'),
            ('Maritime|Agoè-Nyivé', 'Agoè-Nyivé'),
            # =====================================================
            # RÉGION DES PLATEAUX (12 préfectures)
            # =====================================================
            ('Plateaux|Agou', 'Agou'),
            ('Plateaux|Akébou', 'Akébou'),
            ('Plateaux|Amou', 'Amou'),
            ('Plateaux|Anié', 'Anié'),
            ('Plateaux|Danyi', 'Danyi'),
            ('Plateaux|Est-Mono', 'Est-Mono'),
            ('Plateaux|Haho', 'Haho'),
            ('Plateaux|Kloto', 'Kloto'),
            ('Plateaux|Kpélé', 'Kpélé'),
            ('Plateaux|Moyen-Mono', 'Moyen-Mono'),
            ('Plateaux|Ogou', 'Ogou'),
            ('Plateaux|Wawa', 'Wawa'),
            # =====================================================
            # RÉGION CENTRALE (5 préfectures)
            # =====================================================
            ('Centrale|Blitta', 'Blitta'),
            ('Centrale|Mô', 'Mô'),
            ('Centrale|Sotouboua', 'Sotouboua'),
            ('Centrale|Tchamba', 'Tchamba'),
            ('Centrale|Tchaoudjo', 'Tchaoudjo'),
            # =====================================================
            # RÉGION DE LA KARA (7 préfectures)
            # =====================================================
            ('Kara|Assoli', 'Assoli'),
            ('Kara|Bassar', 'Bassar'),
            ('Kara|Binah', 'Binah'),
            ('Kara|Dankpen', 'Dankpen'),
            ('Kara|Doufelgou', 'Doufelgou'),
            ('Kara|Kéran', 'Kéran'),
            ('Kara|Kozah', 'Kozah'),
            # =====================================================
            # RÉGION DES SAVANES (7 préfectures)
            # =====================================================
            ('Savanes|Cinkassé', 'Cinkassé'),
            ('Savanes|Kpendjal', 'Kpendjal'),
            ('Savanes|Kpendjal-Ouest', 'Kpendjal-Ouest'),
            ('Savanes|Oti', 'Oti'),
            ('Savanes|Oti-Sud', 'Oti-Sud'),
            ('Savanes|Tandjouaré', 'Tandjouaré'),
            ('Savanes|Tône', 'Tône'),
        ]
    )
    nationalite = models.CharField(max_length=50, blank=True, default='Togolaise')

    nom_pere = models.CharField(max_length=200, blank=True, verbose_name="Nom du père")
    telephone_pere = models.CharField(max_length=20, blank=True, verbose_name="Téléphone du père")
    profession_pere = models.CharField(max_length=100, blank=True, verbose_name="Profession du père")
    adresse_pere = models.CharField(max_length=255, blank=True, verbose_name="Adresse du père")
    email_pere = models.EmailField(blank=True, verbose_name="Email du père")

    nom_mere = models.CharField(max_length=200, blank=True, verbose_name="Nom de la mère")
    telephone_mere = models.CharField(max_length=20, blank=True, verbose_name="Téléphone de la mère")
    profession_mere = models.CharField(max_length=100, blank=True, verbose_name="Profession de la mère")
    adresse_mere = models.CharField(max_length=255, blank=True, verbose_name="Adresse de la mère")
    email_mere = models.EmailField(blank=True, verbose_name="Email de la mère")

    nom_tuteur = models.CharField(max_length=200, blank=True, verbose_name="Nom du tuteur")
    telephone_tuteur = models.CharField(max_length=20, blank=True, verbose_name="Téléphone du tuteur")
    profession_tuteur = models.CharField(max_length=100, blank=True, verbose_name="Profession du tuteur")
    adresse_tuteur = models.CharField(max_length=255, blank=True, verbose_name="Adresse du tuteur")
    email_tuteur = models.EmailField(blank=True, verbose_name="Email du tuteur")

    adresse = models.CharField(max_length=255, blank=True, verbose_name="Adresse de l'élève")
    photo = models.ImageField(upload_to='eleves/', null=True, blank=True, verbose_name="Photo (passeport)")

    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='nouveau')
    actif = models.BooleanField(default=True)
    date_inscription = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Élève"
        verbose_name_plural = "Élèves"
        ordering = ['nom', 'prenom']
        unique_together = ('etablissement', 'matricule')

    def __str__(self):
        return f"{self.nom} {self.prenom} ({self.matricule})"

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"

    @property
    def age(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_naissance.year - (
            (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
        )

    def inscription_active(self):
        return self.inscriptions.filter(actif=True).first()


class Inscription(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='inscriptions')
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='inscriptions')
    annee_scolaire = models.ForeignKey(AnneeScolaire, on_delete=models.CASCADE, related_name='inscriptions', null=True, blank=True)
    date_inscription = models.DateField(auto_now_add=True)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Inscription"
        verbose_name_plural = "Inscriptions"
        unique_together = ('eleve', 'classe', 'annee_scolaire')

    def __str__(self):
        return f"{self.eleve} → {self.classe}"


# =====================================================
# TRIMESTRES & NOTES
# =====================================================

class Trimestre(models.Model):
    NUMERO_CHOICES = [
        (1, '1er Trimestre'),
        (2, '2ème Trimestre'),
        (3, '3ème Trimestre'),
    ]

    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE, related_name='trimestres')
    numero = models.PositiveSmallIntegerField(choices=NUMERO_CHOICES)
    annee_scolaire = models.CharField(max_length=9, default='2025-2026')
    date_debut = models.DateField()
    date_fin = models.DateField()
    cloture = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Trimestre"
        verbose_name_plural = "Trimestres"
        unique_together = ('etablissement', 'numero', 'annee_scolaire')
        ordering = ['annee_scolaire', 'numero']

    def __str__(self):
        return f"{self.get_numero_display()} — {self.annee_scolaire}"


class Note(models.Model):
    """Une note d'un élève dans une matière pour un trimestre."""
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='notes')
    matiere = models.ForeignKey(Matiere, on_delete=models.CASCADE, related_name='notes')
    trimestre = models.ForeignKey(Trimestre, on_delete=models.CASCADE, related_name='notes')
    enseignant = models.ForeignKey(
        Enseignant, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notes_donnees'
    )
    note_devoir1 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    note_devoir2 = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    note_composition = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    date_saisie = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"
        unique_together = ('eleve', 'matiere', 'trimestre')
        ordering = ['eleve__nom', 'matiere__ordre', 'matiere__nom']

    @property
    def moyenne_devoirs(self):
        notes = [n for n in [self.note_devoir1, self.note_devoir2] if n is not None]
        if not notes:
            return None
        return round(sum(notes) / len(notes), 2)

    @property
    def moyenne_finale(self):
        valeurs = []
        if self.moyenne_devoirs is not None:
            valeurs.append(self.moyenne_devoirs)
        if self.note_composition is not None:
            valeurs.append(self.note_composition)
        if not valeurs:
            return None
        return round(sum(valeurs) / len(valeurs), 2)

    @property
    def moyenne(self):
        return self.moyenne_finale

    def __str__(self):
        m = self.moyenne_finale
        return f"{self.eleve} — {self.matiere} : {m if m is not None else '—'}/20"


# =====================================================
# CONFIGURATION ÉTABLISSEMENT
# =====================================================

class ConfigurationEtablissement(models.Model):
    MODE_EN_TETE_CHOICES = [
        ('textuel', 'Textuel (nom + logo)'),
        ('image', 'Image pré-imprimée (scan)'),
    ]

    etablissement = models.OneToOneField(Etablissement, on_delete=models.CASCADE, related_name='configuration')

    pays = models.CharField(max_length=100, default='République Togolaise')
    devise_nationale = models.CharField(max_length=200, default='Travail - Liberté - Patrie', blank=True)
    ministere = models.CharField(max_length=255, blank=True)
    direction_regionale = models.CharField(max_length=255, blank=True)
    inspection = models.CharField(max_length=255, blank=True)
    prefecture = models.CharField(max_length=100, blank=True)
    commune = models.CharField(max_length=100, blank=True)
    perimetre_pedagogique = models.CharField(max_length=255, blank=True, verbose_name="Périmètre pédagogique")
    commune_administration = models.CharField(max_length=100, blank=True, verbose_name="Commune administrative")

    nom_officiel = models.CharField(max_length=255, blank=True)
    devise_ecole = models.CharField(max_length=200, blank=True)
    mode_en_tete = models.CharField(max_length=20, choices=MODE_EN_TETE_CHOICES, default='textuel')
    en_tete_image = models.ImageField(upload_to='config/en_tetes/', null=True, blank=True)

    nom_chef = models.CharField(max_length=150, blank=True)
    titre_chef = models.CharField(max_length=100, blank=True)
    signature_chef = models.ImageField(upload_to='config/signatures/', null=True, blank=True)
    cachet_ecole = models.ImageField(upload_to='config/cachets/', null=True, blank=True)

    annee_fondation = models.CharField(max_length=20, blank=True)
    autorisation_ouverture = models.CharField(max_length=100, blank=True)
    sceau_ministere = models.ImageField(upload_to='config/sceaux/', null=True, blank=True)
    pied_de_page = models.TextField(blank=True)
    ville_document = models.CharField(max_length=100, blank=True)

    # ⭐ NOUVEAU : Note de passage (modifiable)
    note_passage = models.DecimalField(
        max_digits=4, decimal_places=2, default=10,
        verbose_name="Note de passage",
        help_text="Note minimale pour passer en classe supérieure (par défaut : 10/20)"
    )

    date_mise_a_jour = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration d'établissement"
        verbose_name_plural = "Configurations d'établissement"

    def __str__(self):
        return f"Configuration — {self.etablissement.nom}"

    @property
    def est_complete(self):
        return bool(self.nom_officiel and self.nom_chef and self.titre_chef and self.cachet_ecole)


# =====================================================
# DISCIPLINE (Session 18)
# =====================================================
class IncidentDisciplinaire(models.Model):
    """Signalement d'un incident disciplinaire concernant un élève."""

    TYPE_CHOICES = [
        ('insolence', 'Insolence / manque de respect'),
        ('violence_physique', 'Violence physique'),
        ('violence_verbale', 'Violence verbale'),
        ('absence_non_justifiee', 'Absence non justifiée'),
        ('retard_repete', 'Retard répété'),
        ('tricherie', 'Tricherie'),
        ('vol_degradation', 'Vol / dégradation'),
        ('tenue_non_conforme', 'Tenue non conforme'),
        ('refus_obeissance', "Refus d'obéissance"),
        ('perturbation_cours', 'Perturbation du cours'),
        ('autre', 'Autre'),
    ]

    GRAVITE_CHOICES = [
        ('leger', 'Léger'),
        ('moyen', 'Moyen'),
        ('grave', 'Grave'),
    ]

    STATUT_CHOICES = [
        ('signale', 'Signalé'),
        ('traite', 'Traité'),
        ('classe', 'Classé'),
    ]

    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE,
        related_name='incidents_disciplinaires'
    )
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE,
        related_name='incidents_disciplinaires'
    )
    date_incident = models.DateField()
    heure_incident = models.TimeField(null=True, blank=True)
    type_incident = models.CharField(max_length=30, choices=TYPE_CHOICES)
    gravite = models.CharField(max_length=10, choices=GRAVITE_CHOICES, default='leger')
    description = models.TextField(blank=True)
    signale_par = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='incidents_signales'
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='signale')
    date_signalement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Incident disciplinaire"
        verbose_name_plural = "Incidents disciplinaires"
        ordering = ['-date_incident', '-date_signalement']

    def __str__(self):
        return f"{self.eleve} — {self.get_type_incident_display()} ({self.date_incident})"

    @property
    def nb_sanctions(self):
        return self.sanctions.count()


class Sanction(models.Model):
    """Sanction appliquée suite à un incident disciplinaire."""

    TYPE_CHOICES = [
        ('avertissement_oral', 'Avertissement oral'),
        ('avertissement_ecrit', 'Avertissement écrit'),
        ('travail_supplementaire', 'Travail supplémentaire'),
        ('renvoi_cours', 'Renvoi du cours'),
        ('exclusion_cours', 'Exclusion de cours (1-3 jours)'),
        ('exclusion_temporaire', 'Exclusion temporaire (4-8 jours)'),
        ('exclusion_definitive', 'Exclusion définitive'),
        ('convocation_parents', 'Convocation des parents'),
        ('exclusion', 'Exclusion'),
        ('autre', 'Autre'),
    ]

    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE,
        related_name='sanctions'
    )
    incident = models.ForeignKey(
        IncidentDisciplinaire, on_delete=models.CASCADE,
        related_name='sanctions'
    )
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE,
        related_name='sanctions'
    )
    type_sanction = models.CharField(max_length=30, choices=TYPE_CHOICES)
    description = models.TextField(blank=True)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    decidee_par = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='sanctions_decidees'
    )
    date_decision = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sanction"
        verbose_name_plural = "Sanctions"
        ordering = ['-date_debut', '-date_decision']

    def __str__(self):
        return f"{self.eleve} — {self.get_type_sanction_display()} ({self.date_debut})"

    @property
    def duree_jours(self):
        if self.date_debut and self.date_fin:
            return (self.date_fin - self.date_debut).days + 1
        return None


# =====================================================
# PRÉSENCES (Session 20)
# =====================================================
class Presence(models.Model):
    """Présence journalière d'un élève (1 par jour et par élève)."""

    STATUT_CHOICES = [
        ('present', 'Présent'),
        ('absent', 'Absent'),
        ('retard', 'Retard'),
        ('absent_justifie', 'Absent justifié'),
    ]

    etablissement = models.ForeignKey(
        Etablissement, on_delete=models.CASCADE,
        related_name='presences'
    )
    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE,
        related_name='presences'
    )
    classe = models.ForeignKey(
        Classe, on_delete=models.CASCADE,
        related_name='presences'
    )
    date = models.DateField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='present')
    motif = models.CharField(max_length=255, blank=True)
    saisie_par = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='presences_saisies'
    )
    date_saisie = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
        unique_together = ('eleve', 'date')
        ordering = ['-date', 'eleve__nom', 'eleve__prenom']

    def __str__(self):
        return f"{self.eleve} — {self.date} ({self.get_statut_display()})"
