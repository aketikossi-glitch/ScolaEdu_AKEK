# ScolaEdu_AKEK — Contexte projet

## Stack technique
- Termux + Ubuntu + Python 3.14 + Django 6.1.1 + SQLite
- Chemin : ~/gestion_ecole/
- Langue : Français
- Bootstrap 5 + Bootstrap Icons

## Règles absolues
1. Fichiers COMPLETS (pas de patchs)
2. Format : `cat > chemin << 'FIN_NOM' ... FIN_NOM`
3. Commande serveur : `cd ~/gestion_ecole && python manage.py runserver`
4. Jamais `migrate core zero` (destructif)
5. Avant migration : `cp db.sqlite3 db.sqlite3.backup_$(date +%Y%m%d_%H%M)`

## Architecture
- Multi-tenant strict (chaque établissement isolé)
- 6 rôles : admin_principal, chef_etablissement, secretaire, comptable, enseignant, surveillant
- Apps : core, accounts, dashboard, ecoles, principal, vitrine

## Modèles clés (core/models.py)
- Etablissement : nom, code, ville, bp, telephone, actif
- ProfilUtilisateur : user, role, etablissement
- AnneeScolaire : libelle, en_cours, cloturee
- Trimestre : etablissement, annee_scolaire (CharField!), numero, cloture
- Classe : etablissement, annee_scolaire, nom, niveau, titulaire
- Matiere : etablissement, annee_scolaire, nom, code, coefficient, ordre
- MatiereClasse : classe + matiere + coefficient + enseignant (PIVOT)
- Enseignant : user, etablissement, specialite
- Eleve : matricule, nom, prenom, sexe, photo, statut, actif (booléen!)
- Inscription : eleve, classe, annee_scolaire, actif
- Note : eleve, matiere, trimestre, note_devoir1/2, note_composition
  - moyenne_devoirs = (Dev1+Dev2)/2 (ignore None, compte 0)
  - moyenne_finale = (MoyDevoirs+Compo)/2
- ConfigurationEtablissement : commune, signature_chef, cachet_ecole, note_passage

## Points CRITIQUES
- `Trimestre.annee_scolaire` est un CharField (ex: "2026-2027"), PAS une FK
- `Eleve.actif` (booléen) séparé de `Eleve.statut` (nouveau/redoublant/transfere)
- `MatiereClasse` est le pivot : enseignant ↔ classe ↔ matière
- Filtrage par rôle via : `_get_classes_autorisees()`, `_get_matieres_autorisees()`, `_verifier_acces_classe()`
- Enseignant ne peut saisir QUE pour ses (classe + matière)

## Fichiers clés
- core/entete_document.py : generer_entete_document(config, style, orientation)
- core/export_import.py : exports Excel/CSV/PDF + import
- core/bulletin_pdf.py : exporter_bulletins_pdf() - bulletins complets
- core/admin.py : filtrage automatique par établissement
- accounts/middleware.py : RestrictionAdminDjango + VerificationEtablissementActif

## URLs principales
- /ecole/notes/, /ecole/notes/saisie/, /ecole/notes/verification/
- /ecole/api/matieres/<classe_id>/ (JSON pour filtrage dynamique)
- /ecole/bulletins/, /ecole/bulletins/classe/<id>/trimestre/<id>/pdf/
- /principal/etablissements/, /principal/utilisateurs/

## Sessions terminées
1-2 : Multi-tenant + Auth
3 : Admin Principal (établissements)
3b : Utilisateurs par établissement
4 : Classes (CRUD)
5 : Matières (CRUD)
6 : Matières par classe (affectation)
7 : Élèves + Inscriptions + Import/Export + Photo
8 : Saisie + Vérification des notes
9 : Bulletins PDF (complet)

## Prochaines sessions
1. Fiche élève PDF
2. Relevé de notes classe
3. Cartes scolaires
4. Attestations
5. Listes de classe
6. Module Discipline
7. Module Comptabilité
8. Module Présences
9. Page vérification config

## Lancement serveur
```bash
cd ~/gestion_ecole
python manage.py runserver
