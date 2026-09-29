"""
ScolaEdu_AKEK — Fiche vierge d'inscription (PDF A4 portrait).
Version 11 : armoirie à taille bornée (max 20×20mm), ratio préservé.
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

import os
from django.conf import settings

NOIR = colors.HexColor('#000000')


# =====================================================
# HELPER : taille d'image bornée (ratio préservé)
# =====================================================
def _calc_logo_size_mm(path, max_largeur_mm=20, max_hauteur_mm=20):
    """
    Retourne (width_mm, height_mm) pour l'image, bornée dans la boîte
    max_largeur_mm × max_hauteur_mm, en préservant le ratio d'origine.
    """
    try:
        from PIL import Image
        with Image.open(path) as im:
            w_px, h_px = im.size
        if w_px <= 0 or h_px <= 0:
            return (max_largeur_mm, max_hauteur_mm)
        ratio = w_px / h_px
        # On essaie avec la hauteur max
        h = max_hauteur_mm
        w = h * ratio
        # Si trop large, on contraint par la largeur
        if w > max_largeur_mm:
            w = max_largeur_mm
            h = w / ratio
        return (w, h)
    except Exception:
        return (max_largeur_mm, max_hauteur_mm)


# =====================================================
# CASE À COCHER (mini-table avec bordure noire)
# =====================================================
def _cb():
    """
    Retourne un mini-Table avec bordure noire = case à cocher vide.
    Largeur 3mm × Hauteur 3mm.
    """
    t = Table([[""]], colWidths=[3.5 * mm], rowHeights=[3.5 * mm])
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, NOIR),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# =====================================================
# EN-TÊTE
# =====================================================
def _entete_noir(config=None):
    """
    En-tête avec 3 blocs CENTRÉS :
      - Bloc gauche : Ministère / Direction / Inspection (centré dans sa moitié)
      - Bloc centre : Armoirie (logo établissement ou armoirie Togo)
      - Bloc droite : République Togolaise / Devise (centré dans sa moitié)
    """
    from reportlab.platypus import Image as RLImage

    styles = getSampleStyleSheet()
    # 🎯 Les deux styles sont CENTRÉS
    style_gauche = ParagraphStyle(
        'EG', parent=styles['Normal'],
        alignment=1, fontSize=8.5, leading=11, textColor=NOIR,
    )
    style_droite = ParagraphStyle(
        'ED', parent=styles['Normal'],
        alignment=1, fontSize=8.5, leading=11, textColor=NOIR,
    )

    if config:
        ministere = config.ministere or "MINISTERE DE L'EDUCATION NATIONALE"
        direction = config.direction_regionale or ""
        inspection = config.inspection or ""
    else:
        ministere = "MINISTERE DE L'EDUCATION NATIONALE"
        direction = ""
        inspection = ""

    gauche_parts = [f"<b>{ministere}</b>"]
    if direction:
        gauche_parts.append(f"<b>{direction}</b>")
    if inspection:
        gauche_parts.append(f"<b>{inspection}</b>")

    gauche_html = "<br/>".join(gauche_parts)
    droite_html = (
        "<b>REPUBLIQUE TOGOLAISE</b><br/>"
        "<i>Travail-Liberté-Patrie</i>"
    )

    # ===== Armoirie (taille bornée 20×20mm, ratio préservé) =====
    armoirie_img = None
    try:
        # Priorité 1 : logo établissement
        if config and config.etablissement and config.etablissement.logo:
            try:
                path_logo = config.etablissement.logo.path
                if os.path.exists(path_logo) and os.path.getsize(path_logo) > 0:
                    w_mm, h_mm = _calc_logo_size_mm(path_logo, 20, 20)
                    armoirie_img = RLImage(path_logo, width=w_mm * mm, height=h_mm * mm)
            except Exception:
                pass

        # Priorité 2 : armoirie Togo statique
        if not armoirie_img:
            path_arm = os.path.join(settings.BASE_DIR, 'static', 'images', 'armoiries_togo.png')
            if os.path.exists(path_arm) and os.path.getsize(path_arm) > 0:
                w_mm, h_mm = _calc_logo_size_mm(path_arm, 20, 20)
                armoirie_img = RLImage(path_arm, width=w_mm * mm, height=h_mm * mm)
    except Exception:
        armoirie_img = None

    if not armoirie_img:
        armoirie_img = ''

    # 3 colonnes : gauche / armoirie / droite
    # rowHeights fixe → empêche ReportLab d'étendre la ligne
    conteneur = Table(
        [[Paragraph(gauche_html, style_gauche),
          armoirie_img,
          Paragraph(droite_html, style_droite)]],
        colWidths=[87 * mm, 26 * mm, 87 * mm],
        rowHeights=[22 * mm],
    )
    conteneur.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    return [conteneur, Spacer(1, 8 * mm)]


# =====================================================
# LIGNE AVEC BORDURE POINTILLÉE
# =====================================================
def _ligne(label, largeur_label_mm, largeur_totale_mm=200, hauteur_mm=6,
           valeur="", font_size=9.5):
    styles = getSampleStyleSheet()
    st_label = ParagraphStyle(
        'LBL', parent=styles['Normal'],
        fontSize=font_size, leading=font_size + 2,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    st_valeur = ParagraphStyle(
        'VAL', parent=styles['Normal'],
        fontSize=font_size, leading=font_size + 2,
        textColor=NOIR,
    )

    t = Table(
        [[Paragraph(label, st_label),
          Paragraph(valeur, st_valeur)]],
        colWidths=[largeur_label_mm * mm, (largeur_totale_mm - largeur_label_mm) * mm],
        rowHeights=[hauteur_mm * mm],
    )
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LINEBELOW', (1, 0), (1, 0), 0.5, NOIR),
    ]))
    return t


# =====================================================
# LIGNE AVEC CASES À COCHER (case + texte côte à côte)
# =====================================================
def _option_avec_case(texte):
    """
    Retourne un mini-Table : [ case ] [ texte ]
    → garde la case et le texte alignés.
    """
    styles = getSampleStyleSheet()
    st = ParagraphStyle(
        'OptTxt', parent=styles['Normal'],
        fontSize=9, leading=11, textColor=NOIR,
    )
    t = Table(
        [[_cb(), Paragraph(texte, st)]],
        colWidths=[5 * mm, None],
        rowHeights=[5 * mm],
    )
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def _ligne_options(label, options, largeur_label_mm=45, largeur_totale_mm=200,
                   hauteur_mm=6):
    """
    Ligne : [ Label ] [ case+texte ] [ case+texte ]...
    """
    styles = getSampleStyleSheet()
    st_label = ParagraphStyle(
        'LBL', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, fontName='Helvetica-Bold',
    )

    ligne = [Paragraph(label, st_label)]
    largeur_restante = largeur_totale_mm - largeur_label_mm
    nb_opt = len(options)
    largeur_par_opt = largeur_restante / nb_opt if nb_opt > 0 else 0

    for opt in options:
        ligne.append(_option_avec_case(opt))

    col_widths = [largeur_label_mm * mm] + [largeur_par_opt * mm] * nb_opt

    t = Table([ligne], colWidths=col_widths, rowHeights=[hauteur_mm * mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# =====================================================
# LIGNE CODE ÉTABLISSEMENT
# =====================================================
def _ligne_code_etab(largeur_label_mm=45, largeur_totale_mm=200):
    """
    Ligne : [ Label ][ case ][ case ][ case ]...
    13 cellules avec bordure noire → chaque case = 1 chiffre du code.
    """
    styles = getSampleStyleSheet()
    st_label = ParagraphStyle(
        'LBL3', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    st_cell = ParagraphStyle(
        'CellCode', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, alignment=1,
    )

    nb_cases = 13
    largeur_restante = largeur_totale_mm - largeur_label_mm
    largeur_case = largeur_restante / nb_cases

    # Ligne
    ligne = [Paragraph("Code Etablissement :", st_label)]
    for _ in range(nb_cases):
        ligne.append(Paragraph("", st_cell))

    col_widths = [largeur_label_mm * mm] + [largeur_case * mm] * nb_cases

    t = Table([ligne], colWidths=col_widths, rowHeights=[5 * mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        # Bordures autour de chaque case (à partir de la 2e colonne)
        ('GRID', (1, 0), (-1, -1), 0.5, NOIR),
    ]))
    return t


# =====================================================
# LIGNE : Niveau + Classe + Nouveau/Redoublant
# =====================================================
def _ligne_niveau(largeur_totale_mm=200):
    styles = getSampleStyleSheet()
    st = ParagraphStyle(
        'Niv', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR,
    )
    st_b = ParagraphStyle(
        'NivB', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR, fontName='Helvetica-Bold',
    )

    ligne = [
        Paragraph("<b>Niveau ¹ :</b>", st_b),
        Paragraph("......................", st),
        Paragraph("<b>Classe ² :</b>", st_b),
        Paragraph("......................", st),
        _option_avec_case("Nouveau"),
        _option_avec_case("Redoublant"),
    ]
    col_widths = [18 * mm, 40 * mm, 18 * mm, 40 * mm, 42 * mm, 42 * mm]
    t = Table([ligne], colWidths=col_widths, rowHeights=[6 * mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# =====================================================
# LIGNE : Date naissance + Sexe
# =====================================================
def _ligne_date_sexe(largeur_totale_mm=200):
    styles = getSampleStyleSheet()
    st = ParagraphStyle(
        'DS', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR,
    )
    st_b = ParagraphStyle(
        'DSB', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR, fontName='Helvetica-Bold',
    )

    ligne = [
        Paragraph("<b>Date de Naissance :</b>", st_b),
        Paragraph("....../....../................", st),
        Paragraph("<b>Sexe :</b>", st_b),
        _option_avec_case("Masculin"),
        _option_avec_case("Féminin"),
    ]
    col_widths = [38 * mm, 55 * mm, 20 * mm, 43 * mm, 44 * mm]
    t = Table([ligne], colWidths=col_widths, rowHeights=[6 * mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# =====================================================
# SITUATION HANDICAP (bloc 2 lignes alignées)
# =====================================================
def _bloc_handicap(largeur_totale_mm=200):
    """
    Structure :
        Ligne 1 : Situation handicap : [Aucun □] [Moteur Léger □] [Mal Voyant □] [Mal Entendant □] [Déficient Intellectuel □]
        Ligne 2 :                      [Moteur Lourd □] [Non Voyant □] [Non Entendant □] [Albinos □]
    → 5 colonnes par ligne, largeurs strictes.
    """
    styles = getSampleStyleSheet()
    st_label = ParagraphStyle(
        'HDL', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, fontName='Helvetica-Bold',
    )

    largeur_label = 35
    largeur_restante = largeur_totale_mm - largeur_label
    largeur_col = largeur_restante / 5    # 5 colonnes
    col_widths = [largeur_label * mm] + [largeur_col * mm] * 5

    opt_l1 = [
        _option_avec_case("Aucun"),
        _option_avec_case("Moteur Léger"),
        _option_avec_case("Mal Voyant"),
        _option_avec_case("Mal Entendant"),
        _option_avec_case("Déficient Intel."),
    ]
    opt_l2 = [
        _option_avec_case("Moteur Lourd"),
        _option_avec_case("Non Voyant"),
        _option_avec_case("Non Entendant"),
        _option_avec_case("Albinos"),
        "",
    ]

    ligne1 = [Paragraph("Situation handicap :", st_label)] + opt_l1
    ligne2 = [Paragraph("", st_label)] + opt_l2

    t = Table([ligne1, ligne2], colWidths=col_widths, rowHeights=[5.5 * mm, 5.5 * mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# =====================================================
# GÉNÉRATION
# =====================================================
def exporter_fiche_vierge_pdf(etablissement, config=None, utilisateur=None, annee_courante=None):
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=0.5 * cm, rightMargin=0.5 * cm,
        topMargin=0.5 * cm, bottomMargin=0.5 * cm,
    )

    elements = []
    styles = getSampleStyleSheet()
    LARGEUR = 200

    # ===== En-tête =====
    elements.extend(_entete_noir(config))
    elements.append(Spacer(1, 4 * mm))

    # ===== Styles =====
    titre_style = ParagraphStyle(
        'Titre', parent=styles['Normal'],
        fontSize=12, leading=14, alignment=1,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=0,
        textColor=NOIR, fontName='Helvetica-Bold',
        spaceBefore=1, spaceAfter=1,
    )
    signature_style = ParagraphStyle(
        'Signature', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=2,
        textColor=NOIR, fontName='Helvetica-Oblique',
    )

    # ===== Titre principal (encadré juste autour du texte) =====
    # On utilise un Table à 3 colonnes : [spacer] [titre] [spacer]
    # → la colonne centrale a la largeur exacte du texte
    titre_cell = Table(
        [[Paragraph("FICHE UNIQUE D'INSCRIPTION D'UN ÉLÈVE", titre_style)]],
        colWidths=[None],   # largeur auto
    )
    titre_cell.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 0.8, NOIR),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    # Centrer le bloc titre dans la largeur de la page
    titre_bloc = Table(
        [['', titre_cell, '']],
        colWidths=[(LARGEUR - 105) / 2 * mm, 105 * mm, (LARGEUR - 105) / 2 * mm],
    )
    titre_bloc.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(titre_bloc)
    elements.append(Spacer(1, 2 * mm))

    # =====================================================
    # SECTION 1
    # =====================================================
    elements.append(Paragraph(
        "1- <b><u>Informations sur l'établissement</u></b> "
        "<font size='7.5'><i>( Réservé à l'administration de l'Etablissement )</i></font>",
        section_style
    ))

    elements.append(_ligne("Direction Régionale :", 45, LARGEUR))
    elements.append(_ligne("Inspection :", 45, LARGEUR))
    elements.append(_ligne("Périmètre Pédagogique :", 45, LARGEUR))
    elements.append(_ligne("Commune :", 45, LARGEUR))
    elements.append(_ligne("Etablissement :", 45, LARGEUR))
    elements.append(_ligne_code_etab(45, LARGEUR))

    elements.append(_ligne_options(
        "Ordre d'Enseignement :",
        ["Public", "Laïc", "Confessionnel", "Communautaire"],
        largeur_label_mm=45, largeur_totale_mm=LARGEUR
    ))

    elements.append(_ligne_options(
        "Cycle d'Enseignement :",
        ["Préscolaire", "Primaire", "Secondaire I", "Secondaire II"],
        largeur_label_mm=45, largeur_totale_mm=LARGEUR
    ))
    elements.append(Spacer(1, 2 * mm))

    # =====================================================
    # SECTION 2
    # =====================================================
    elements.append(Paragraph(
        "2- <b><u>Informations sur l'élève</u></b>",
        section_style
    ))

    elements.append(_ligne_niveau(LARGEUR))
    elements.append(_ligne("Nom :", 18, LARGEUR))
    elements.append(_ligne("Prénoms :", 22, LARGEUR))
    elements.append(_ligne_date_sexe(LARGEUR))
    elements.append(_ligne("Lieu de Naissance :", 38, LARGEUR))

    elements.append(_ligne_options(
        "Situation Famille de l'élève :",
        ["Parents Vivants", "Orphelin", "Orphelin Mère", "Orphelin Père"],
        largeur_label_mm=50, largeur_totale_mm=LARGEUR
    ))

    elements.append(_ligne("Adresse Elève :", 30, LARGEUR))
    elements.append(_ligne("Préfecture de Naissance ³ :", 52, LARGEUR))
    elements.append(_ligne("Pays de Naissance :", 38, LARGEUR))

    # Situation handicap
    elements.append(_bloc_handicap(LARGEUR))
    elements.append(Spacer(1, 2 * mm))

    # =====================================================
    # SECTION 3
    # =====================================================
    elements.append(Paragraph(
        "3- <b><u>Informations sur les parents de l'élève</u></b>",
        section_style
    ))

    header_parents = [
        Paragraph("", styles['Normal']),
        Paragraph("<i>Père</i>", ParagraphStyle(
            'HP', parent=styles['Normal'], alignment=1, fontSize=10, fontName='Helvetica-Oblique')),
        Paragraph("<i>Mère</i>", ParagraphStyle(
            'HM', parent=styles['Normal'], alignment=1, fontSize=10, fontName='Helvetica-Oblique')),
    ]
    parents_data = [
        [Paragraph("<b>Nom</b>", styles['Normal']), Paragraph("", styles['Normal']), Paragraph("", styles['Normal'])],
        [Paragraph("<b>Prénoms</b>", styles['Normal']), Paragraph("", styles['Normal']), Paragraph("", styles['Normal'])],
        [Paragraph("<b>Téléphone</b>", styles['Normal']), Paragraph("", styles['Normal']), Paragraph("", styles['Normal'])],
        [Paragraph("<b>Profession ⁴</b>", styles['Normal']), Paragraph("", styles['Normal']), Paragraph("", styles['Normal'])],
    ]
    parents_table = Table(
        [header_parents] + parents_data,
        colWidths=[35 * mm, 82.5 * mm, 82.5 * mm],
        rowHeights=[7 * mm] * 5,
    )
    parents_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, NOIR),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(parents_table)
    elements.append(Spacer(1, 2 * mm))

    # =====================================================
    # SECTION 4
    # =====================================================
    elements.append(Paragraph(
        "4- <b><u>Personne à prévenir en cas d'urgence pour l'élève (Tuteur)</u></b>",
        section_style
    ))

    elements.append(_ligne("Nom :", 18, LARGEUR))
    elements.append(_ligne("Prénoms :", 22, LARGEUR))
    elements.append(_ligne("Téléphone :", 25, LARGEUR))
    elements.append(_ligne("Profession :", 25, LARGEUR))
    elements.append(_ligne("Adresse :", 22, LARGEUR))

    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("Signature du parent de l'élève", signature_style))

    # ===== Callback : pied de page =====
    def dessiner_pied(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(NOIR)
        canvas_obj.setLineWidth(0.5)

        y_bas = 8 * mm
        largeur = A4[0] - 2 * (0.5 * cm)
        x_gauche = 0.5 * cm

        canvas_obj.line(x_gauche, y_bas + 14 * mm, x_gauche + largeur, y_bas + 14 * mm)

        canvas_obj.setFont('Helvetica', 6.5)
        canvas_obj.setFillColor(NOIR)

        notes = [
            "1 Exemple : JE1, JE2, CP1, CP2, CE1, CE2, CM1, CM2, 6eme, 5eme, 4eme, 3eme, 2nde, 1ere, Tle",
            "2 Exemple : CP1 A, CP1 B, CP1 C, CM1 A, CM1 B ........ 6eme A, 6eme B, 6eme C, 5eme A, 5eme B ........, 2nde A1, 2nde A2, 2nde A3, 1ere C4, 1ere D1, 1ere C4 2...",
            "3 pour les etrangers, mettre « ETRANGER »",
            "4 Exemple : Employe dans le public, Employe dans le prive, Force de defense et de securite, Profession liberale",
        ]

        y = y_bas + 11 * mm
        for note in notes:
            canvas_obj.drawString(x_gauche, y, note)
            y -= 3 * mm

        canvas_obj.restoreState()

    doc.onFirstPage = dessiner_pied
    doc.onLaterPages = dessiner_pied

    doc.build(elements)
    output.seek(0)
    return output
