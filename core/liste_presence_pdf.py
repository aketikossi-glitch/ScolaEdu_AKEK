"""
ScolaEdu_AKEK — Liste de présence d'une classe PDF (A4 portrait).
Session 17b : feuille d'appel vierge avec 7 colonnes pour saisie manuscrite.
Version 4 :
  - En-tête 2 blocs, chacun CENTRÉ dans sa moitié
  - Colonne Statut élargie (16mm) → « Statut » tient sur une ligne
  - Tableau : tout en GRAS taille 11.5, fond blanc total
  - Ligne TOTAL supprimée
"""
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)


# =====================================================
# COULEURS
# =====================================================
NOIR = colors.HexColor('#000000')


# =====================================================
# HELPERS
# =====================================================
def _statut_lettre(eleve):
    """Retourne N (nouveau/transféré) ou R (redoublant)."""
    if eleve.statut == 'redoublant':
        return 'R'
    return 'N'


def _sexe_lettre(eleve):
    """Retourne M ou F."""
    return eleve.sexe or '—'


def _calculer_liste(classe):
    """Retourne la liste des élèves avec leurs données minimales."""
    from core.models import Inscription

    inscriptions = list(
        Inscription.objects.filter(classe=classe, actif=True)
        .select_related('eleve')
        .order_by('eleve__nom', 'eleve__prenom')
    )

    eleves_data = []
    for insc in inscriptions:
        eleve = insc.eleve
        eleves_data.append({
            'nom_complet': f"{(eleve.nom or '').upper()} {eleve.prenom or ''}".strip(),
            'sexe': _sexe_lettre(eleve),
            'statut': _statut_lettre(eleve),
        })

    return {'eleves_data': eleves_data}


# =====================================================
# EN-TÊTE 2 BLOCS (chacun centré dans sa moitié)
# =====================================================
def _entete_deux_blocs(config, etablissement):
    """
    En-tête sobre en 2 blocs :
      - Gauche  : Ministère / DRE / IESG / Nom établissement (centré dans sa moitié)
      - Droite  : République Togolaise / Devise (centré dans sa moitié)
    """
    styles = getSampleStyleSheet()
    style_gauche = ParagraphStyle(
        'EnteteG', parent=styles['Normal'],
        fontSize=8.5, leading=11, alignment=1,
        textColor=NOIR,
    )
    style_droite = ParagraphStyle(
        'EnteteD', parent=styles['Normal'],
        fontSize=8.5, leading=11, alignment=1,
        textColor=NOIR,
    )

    # ===== Valeurs =====
    ministere = "MINISTÈRE DE L'ÉDUCATION NATIONALE"
    direction = ""
    inspection = ""
    if config:
        ministere = (config.ministere or ministere).upper()
        direction = (config.direction_regionale or "").upper()
        inspection = (config.inspection or "").upper()

    nom_etab = ""
    if etablissement:
        nom_etab = (etablissement.nom or "").upper()

    pays = "RÉPUBLIQUE TOGOLAISE"
    devise = "Travail - Liberté - Patrie"
    if config:
        pays = (config.pays or pays).upper()
        devise = config.devise_nationale or devise

    # ===== Bloc gauche =====
    gauche_parts = [f"<b>{ministere}</b>"]
    if direction:
        gauche_parts.append(f"<b>{direction}</b>")
    if inspection:
        gauche_parts.append(f"<b>{inspection}</b>")
    if nom_etab:
        gauche_parts.append(f"<b>{nom_etab}</b>")
    gauche_html = "<br/>".join(gauche_parts)

    # ===== Bloc droite =====
    droite_html = f"<b>{pays}</b><br/><i>{devise}</i>"

    # ===== Tableau 2 colonnes (50/50), chacune CENTRÉE =====
    tbl = Table(
        [[
            Paragraph(gauche_html, style_gauche),
            Paragraph(droite_html, style_droite),
        ]],
        colWidths=[95 * mm, 95 * mm],
    )
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return [tbl, Spacer(1, 4 * mm)]


# =====================================================
# GÉNÉRATION PDF
# =====================================================
def exporter_liste_presence_pdf(classe, config=None, utilisateur=None,
                                 annee_libelle=None, etablissement=None):
    """
    Génère un PDF A4 portrait : feuille de présence vierge pour la classe.
    """
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    # ===== En-tête 2 blocs =====
    elements.extend(_entete_deux_blocs(config, etablissement))

    # ===== Titre principal =====
    titre_style = ParagraphStyle(
        'Titre', parent=styles['Normal'],
        fontSize=14, leading=16, alignment=1,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    elements.append(Paragraph("LISTE DE PRÉSENCE", titre_style))
    elements.append(Spacer(1, 2 * mm))

    # ===== Sous-titre : Classe à gauche + Année à droite =====
    style_gauche_titre = ParagraphStyle(
        'SousG', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=0,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    style_droite_titre = ParagraphStyle(
        'SousD', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=2,
        textColor=NOIR, fontName='Helvetica-Bold',
    )

    sous_titre_tbl = Table(
        [[
            Paragraph(f"Classe : {classe.nom}", style_gauche_titre),
            Paragraph(f"Année scolaire : {annee_libelle or '—'}", style_droite_titre),
        ]],
        colWidths=[95 * mm, 95 * mm],
    )
    sous_titre_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(sous_titre_tbl)
    elements.append(Spacer(1, 4 * mm))

    # ===== Calcul des données =====
    data = _calculer_liste(classe)
    eleves_data = data['eleves_data']

    # ===== Styles des cellules (TOUT EN GRAS 11.5) =====
    style_cell = ParagraphStyle(
        'Cell', parent=styles['Normal'],
        fontSize=11.5, leading=13.5, alignment=1,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    style_cell_left = ParagraphStyle(
        'CellL', parent=styles['Normal'],
        fontSize=11.5, leading=13.5, alignment=0,
        textColor=NOIR, fontName='Helvetica-Bold',
    )

    # ===== En-tête du tableau =====
    header = [
        Paragraph("N°", style_cell),
        Paragraph("Nom &amp; Prénom", style_cell),
        Paragraph("Sexe", style_cell),
        Paragraph("Statut", style_cell),
        Paragraph("", style_cell),
        Paragraph("", style_cell),
        Paragraph("", style_cell),
        Paragraph("", style_cell),
        Paragraph("", style_cell),
        Paragraph("", style_cell),
        Paragraph("", style_cell),
    ]
    table_data = [header]

    # ===== Lignes élèves =====
    for idx, e in enumerate(eleves_data, start=1):
        ligne = [
            Paragraph(str(idx), style_cell),
            Paragraph(e['nom_complet'], style_cell_left),
            Paragraph(e['sexe'], style_cell),
            Paragraph(e['statut'], style_cell),
            Paragraph("", style_cell),
            Paragraph("", style_cell),
            Paragraph("", style_cell),
            Paragraph("", style_cell),
            Paragraph("", style_cell),
            Paragraph("", style_cell),
            Paragraph("", style_cell),
        ]
        table_data.append(ligne)

    # ===== Largeurs des colonnes (total ≈ 190 mm) =====
    # N° : 10mm — Nom : 66mm — Sexe : 13mm — Statut : 16mm — 7 × 12.14mm ≈ 85mm
    largeur_7_cols = (190 - 10 - 66 - 13 - 16) / 7  # = 85/7 ≈ 12.14 mm
    col_widths = [
        10 * mm,    # N°
        66 * mm,    # Nom & Prénom
        13 * mm,    # Sexe
        16 * mm,    # Statut (élargie pour éviter le retour à la ligne)
    ] + [largeur_7_cols * mm] * 7

    # ===== Construction du tableau =====
    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # En-tête
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 0), (-1, 0), NOIR),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        # Corps
        ('VALIGN', (0, 1), (-1, -1), 'MIDDLE'),
        # Grille complète (bordures noires)
        ('GRID', (0, 0), (-1, -1), 0.5, NOIR),
        ('BOX', (0, 0), (-1, -1), 1, NOIR),
        # Fond BLANC total
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))

    elements.append(tbl)

    doc.build(elements)
    output.seek(0)
    return output
