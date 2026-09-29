"""
ScolaEdu_AKEK — Fiche individuelle de l'élève (PDF A4 portrait).
Version 6 : Format officiel togolais "FICHE UNIQUE D'INSCRIPTION D'UN ÉLÈVE".
  - Alignement parfait via helpers de fiche_preremplie_pdf
  - Libellés en GRAS noir, valeurs en ITALIQUE noir
  - Titre encadré largeur ajustée (115 mm) fond bleu clair
  - Tableau parents : bordures bleues, en-tête bleu clair
  - Cases à cocher dessinées (bordure noire)
  - Marges 5mm partout
  - Pied de page avec attestation d'inscription (centré, gras italique)
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

from core.entete_document import generer_entete_document


BLEU_MARINE = colors.HexColor('#1E3A8A')
BLEU_CLAIR  = colors.HexColor('#DBEAFE')
GRIS_TEXTE  = colors.HexColor('#64748B')
NOIR        = colors.HexColor('#000000')


def _v(v, defaut=""):
    if v is None:
        return defaut
    s = str(v).strip()
    return s if s else defaut


def _fmt_date(d):
    if not d:
        return ""
    try:
        return d.strftime('%d/%m/%Y')
    except Exception:
        return str(d)


def _split_nom_prenoms(nom_complet):
    """Sépare 'KOSSI Afio' en ('KOSSI', 'Afio')."""
    if not nom_complet:
        return ('', '')
    parts = nom_complet.strip().split(' ', 1)
    if len(parts) == 1:
        return (parts[0], '')
    return (parts[0], parts[1])


# =====================================================
# CASE À COCHER (mini-table bordée noire)
# =====================================================
def _cb_vide():
    t = Table([[""]], colWidths=[3.5 * mm], rowHeights=[3.5 * mm])
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, NOIR),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


def _cb_coche():
    """Case cochée : croix 'x' noire."""
    st = ParagraphStyle(
        'X', fontSize=8, leading=9, alignment=1,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    t = Table(
        [[Paragraph("x", st)]],
        colWidths=[3.5 * mm], rowHeights=[3.5 * mm],
    )
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, NOIR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# =====================================================
# LIGNE LABEL/VALEUR ALIGNÉE
# =====================================================
def _ligne(label, largeur_label_mm, largeur_totale_mm=200, hauteur_mm=6,
           valeur=""):
    """Ligne alignée : label (gras noir) / valeur (italique noir)."""
    styles = getSampleStyleSheet()
    st_label = ParagraphStyle(
        'LBL', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    st_valeur = ParagraphStyle(
        'VAL', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, fontName='Helvetica-Oblique',
    )

    t = Table(
        [[Paragraph(label, st_label),
          Paragraph(valeur or "—", st_valeur)]],
        colWidths=[largeur_label_mm * mm, (largeur_totale_mm - largeur_label_mm) * mm],
        rowHeights=[hauteur_mm * mm],
    )
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    return t


# =====================================================
# OPTION AVEC CASE
# =====================================================
def _option_avec_case(texte, coche=False):
    styles = getSampleStyleSheet()
    st = ParagraphStyle(
        'OptTxt', parent=styles['Normal'],
        fontSize=9, leading=11, textColor=NOIR,
        fontName='Helvetica-Oblique',
    )
    case = _cb_coche() if coche else _cb_vide()
    t = Table(
        [[case, Paragraph(texte, st)]],
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


def _ligne_options(label, options_avec_etat, largeur_label_mm=45,
                    largeur_totale_mm=200, hauteur_mm=6):
    styles = getSampleStyleSheet()
    st_label = ParagraphStyle(
        'LBL', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, fontName='Helvetica-Bold',
    )

    ligne = [Paragraph(label, st_label)]
    largeur_restante = largeur_totale_mm - largeur_label_mm
    nb_opt = len(options_avec_etat)
    largeur_par_opt = largeur_restante / nb_opt if nb_opt > 0 else 0

    for texte, coche in options_avec_etat:
        ligne.append(_option_avec_case(texte, coche))

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
# LIGNE CODE ÉTABLISSEMENT (13 cases)
# =====================================================
def _ligne_code_etab(valeur="", largeur_label_mm=45, largeur_totale_mm=200):
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
        fontName='Helvetica-Oblique',
    )

    nb_cases = 13
    largeur_restante = largeur_totale_mm - largeur_label_mm
    largeur_case = largeur_restante / nb_cases

    valeur_str = str(valeur)[:nb_cases] if valeur else ""
    ligne = [Paragraph("Code Etablissement :", st_label)]
    for i in range(nb_cases):
        char = valeur_str[i] if i < len(valeur_str) else ""
        ligne.append(Paragraph(char, st_cell))

    col_widths = [largeur_label_mm * mm] + [largeur_case * mm] * nb_cases

    t = Table([ligne], colWidths=col_widths, rowHeights=[5 * mm])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('GRID', (1, 0), (-1, -1), 0.5, NOIR),
    ]))
    return t


# =====================================================
# LIGNE : Niveau + Classe + Nouveau/Redoublant
# =====================================================
def _ligne_niveau(niveau="", classe="", est_nouveau=False, est_redoublant=False,
                   largeur_totale_mm=200):
    styles = getSampleStyleSheet()
    st = ParagraphStyle(
        'Niv', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR,
        fontName='Helvetica-Oblique',
    )
    st_b = ParagraphStyle(
        'NivB', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR, fontName='Helvetica-Bold',
    )

    ligne = [
        Paragraph("<b>Niveau ¹ :</b>", st_b),
        Paragraph(niveau or "—", st),
        Paragraph("<b>Classe ² :</b>", st_b),
        Paragraph(classe or "—", st),
        _option_avec_case("Nouveau", est_nouveau),
        _option_avec_case("Redoublant", est_redoublant),
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
def _ligne_date_sexe(date_naiss="", est_masculin=False, est_feminin=False,
                      largeur_totale_mm=200):
    styles = getSampleStyleSheet()
    st = ParagraphStyle(
        'DS', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR,
        fontName='Helvetica-Oblique',
    )
    st_b = ParagraphStyle(
        'DSB', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR, fontName='Helvetica-Bold',
    )

    ligne = [
        Paragraph("<b>Date de Naissance :</b>", st_b),
        Paragraph(date_naiss or "—", st),
        Paragraph("<b>Sexe :</b>", st_b),
        _option_avec_case("Masculin", est_masculin),
        _option_avec_case("Féminin", est_feminin),
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
# BLOC HANDICAP (2 lignes : 5 + 4)
# =====================================================
def _bloc_handicap(largeur_totale_mm=200):
    styles = getSampleStyleSheet()
    st_label = ParagraphStyle(
        'HDL', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, fontName='Helvetica-Bold',
    )

    largeur_label = 35
    largeur_restante = largeur_totale_mm - largeur_label
    largeur_col = largeur_restante / 5
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
def exporter_fiche_eleve_pdf(eleve, config=None, utilisateur=None, annee_courante=None):
    """Génère la fiche officielle togolaise."""
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=0.5 * cm, rightMargin=0.5 * cm,
        topMargin=0.5 * cm, bottomMargin=1.2 * cm,
    )

    elements = []
    styles = getSampleStyleSheet()
    LARGEUR = 200

    # ===== En-tête officiel =====
    elements.extend(generer_entete_document(config, style='complet', orientation='portrait'))
    elements.append(Spacer(1, 3 * mm))

    # ===== Styles =====
    titre_style = ParagraphStyle(
        'Titre', parent=styles['Normal'],
        fontSize=12, leading=14, alignment=1,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=0,
        textColor=NOIR, fontName='Helvetica-Bold',
        spaceBefore=2, spaceAfter=2,
    )
    signature_style = ParagraphStyle(
        'Signature', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=2,
        textColor=NOIR, fontName='Helvetica-Oblique',
    )

    # ===== Titre principal (encadré ajusté au texte, 115mm) =====
    titre_cell = Table(
        [[Paragraph("FICHE UNIQUE D'INSCRIPTION D'UN ÉLÈVE", titre_style)]],
        colWidths=[115 * mm],
        rowHeights=[8 * mm],
    )
    titre_cell.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLEU_CLAIR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 0.8, BLEU_MARINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    titre_bloc = Table(
        [['', titre_cell, '']],
        colWidths=[(LARGEUR - 115) / 2 * mm, 115 * mm, (LARGEUR - 115) / 2 * mm],
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

    # ===== Données =====
    etab = eleve.etablissement
    annee_libelle = annee_courante or "—"
    inscription = eleve.inscriptions.filter(actif=True).select_related('classe').first()
    classe_nom = inscription.classe.nom if inscription and inscription.classe else ""
    niveau_nom = inscription.classe.get_niveau_display() if inscription and inscription.classe else ""

    est_nouveau = eleve.statut == 'nouveau'
    est_redoublant = eleve.statut == 'redoublant'
    est_masculin = eleve.sexe == 'M'
    est_feminin = eleve.sexe == 'F'

    date_naiss_txt = _fmt_date(eleve.date_naissance)

    direction_reg = _v(config.direction_regionale if config else "", "")
    inspection = _v(config.inspection if config else "", "")
    perimetre = _v(config.perimetre_pedagogique if config else "", "")
    commune_admin = _v(config.commune_administration if config else "", "")
    nom_etab = _v(etab.nom, "")
    code_etab = _v(etab.code, "")

    type_etab = (etab.type_etablissement or "").lower() if etab else ""
    cycle_prescolaire = type_etab == 'maternelle'
    cycle_primaire = type_etab == 'primaire'
    cycle_sec1 = type_etab in ('college', 'complexe')
    cycle_sec2 = type_etab in ('lycee', 'complexe')

    # =====================================================
    # SECTION 1
    # =====================================================
    elements.append(Paragraph(
        "1- <b>Informations sur l'établissement</b>",
        section_style
    ))

    # ⚠️ TOUS les libellés font 45mm → alignement parfait des ':'
    elements.append(_ligne("Direction Régionale :", 45, LARGEUR, 6, direction_reg))
    elements.append(_ligne("Inspection :", 45, LARGEUR, 6, inspection))
    elements.append(_ligne("Périmètre Pédagogique :", 45, LARGEUR, 6, perimetre))
    elements.append(_ligne("Commune :", 45, LARGEUR, 6, commune_admin))
    elements.append(_ligne("Etablissement :", 45, LARGEUR, 6, nom_etab))
    elements.append(_ligne_code_etab(valeur=code_etab, largeur_label_mm=45,
                                      largeur_totale_mm=LARGEUR))

    elements.append(_ligne_options(
        "Ordre d'Enseignement :",
        [("Public", False), ("Laïc", False),
         ("Confessionnel", False), ("Communautaire", False)],
        largeur_label_mm=45, largeur_totale_mm=LARGEUR
    ))

    elements.append(_ligne_options(
        "Cycle d'Enseignement :",
        [("Préscolaire", cycle_prescolaire),
         ("Primaire", cycle_primaire),
         ("Secondaire I", cycle_sec1),
         ("Secondaire II", cycle_sec2)],
        largeur_label_mm=45, largeur_totale_mm=LARGEUR
    ))
    elements.append(Spacer(1, 2 * mm))

    # =====================================================
    # SECTION 2
    # =====================================================
    elements.append(Paragraph(
        "2- <b>Informations sur l'élève</b>",
        section_style
    ))

    elements.append(_ligne_niveau(
        niveau=niveau_nom, classe=classe_nom,
        est_nouveau=est_nouveau, est_redoublant=est_redoublant,
        largeur_totale_mm=LARGEUR
    ))
    elements.append(_ligne("Nom :", 45, LARGEUR, 6, (eleve.nom or "").upper()))
    elements.append(_ligne("Prénoms :", 45, LARGEUR, 6, eleve.prenom or ""))
    elements.append(_ligne_date_sexe(
        date_naiss=date_naiss_txt,
        est_masculin=est_masculin, est_feminin=est_feminin,
        largeur_totale_mm=LARGEUR
    ))
    elements.append(_ligne("Lieu de Naissance :", 45, LARGEUR, 6, eleve.lieu_naissance or ""))

    elements.append(_ligne_options(
        "Situation Famille de l'élève :",
        [("Parents Vivants", False), ("Orphelin", False),
         ("Orphelin Mère", False), ("Orphelin Père", False)],
        largeur_label_mm=45, largeur_totale_mm=LARGEUR
    ))

    elements.append(_ligne("Adresse Elève :", 45, LARGEUR, 6, eleve.adresse or ""))
    elements.append(_ligne("Préfecture de Naissance :", 45, LARGEUR, 6,
                            eleve.get_prefecture_naissance_display() or ""))
    elements.append(_ligne("Pays de Naissance :", 45, LARGEUR, 6, eleve.nationalite or ""))

    elements.append(_bloc_handicap(LARGEUR))
    elements.append(Spacer(1, 2 * mm))

    # =====================================================
    # SECTION 3 — PARENTS
    # =====================================================
    elements.append(Paragraph(
        "3- <b>Informations sur les parents de l'élève</b>",
        section_style
    ))

    st_cell_val = ParagraphStyle(
        'CellVal', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR,
        fontName='Helvetica-Oblique',
    )
    st_cell_label = ParagraphStyle(
        'CellLabel', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR, fontName='Helvetica-Bold',
    )
    st_header = ParagraphStyle(
        'Hdr', parent=styles['Normal'],
        fontSize=10, leading=12, textColor=BLEU_MARINE,
        alignment=1, fontName='Helvetica-Bold',
    )

    nom_pere, prenom_pere = _split_nom_prenoms(eleve.nom_pere)
    nom_mere, prenom_mere = _split_nom_prenoms(eleve.nom_mere)

    header_parents = [
        Paragraph("", styles['Normal']),
        Paragraph("<b>Père</b>", st_header),
        Paragraph("<b>Mère</b>", st_header),
    ]
    parents_data = [
        [Paragraph("<b>Nom</b>", st_cell_label),
         Paragraph(nom_pere or "—", st_cell_val),
         Paragraph(nom_mere or "—", st_cell_val)],
        [Paragraph("<b>Prénoms</b>", st_cell_label),
         Paragraph(prenom_pere or "—", st_cell_val),
         Paragraph(prenom_mere or "—", st_cell_val)],
        [Paragraph("<b>Téléphone</b>", st_cell_label),
         Paragraph(eleve.telephone_pere or "—", st_cell_val),
         Paragraph(eleve.telephone_mere or "—", st_cell_val)],
        [Paragraph("<b>Profession</b>", st_cell_label),
         Paragraph(eleve.profession_pere or "—", st_cell_val),
         Paragraph(eleve.profession_mere or "—", st_cell_val)],
    ]
    parents_table = Table(
        [header_parents] + parents_data,
        colWidths=[35 * mm, 82.5 * mm, 82.5 * mm],
        rowHeights=[6.5 * mm] * 5,
    )
    parents_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (0, 0), (-1, 0), BLEU_CLAIR),
        ('GRID', (0, 0), (-1, -1), 0.5, BLEU_MARINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(parents_table)
    elements.append(Spacer(1, 2 * mm))

    # =====================================================
    # SECTION 4 — TUTEUR
    # =====================================================
    elements.append(Paragraph(
        "4- <b>Personne à prévenir en cas d'urgence pour l'élève (Tuteur)</b>",
        section_style
    ))

    nom_tuteur, prenom_tuteur = _split_nom_prenoms(eleve.nom_tuteur)

    elements.append(_ligne("Nom :", 45, LARGEUR, 6, nom_tuteur))
    elements.append(_ligne("Prénoms :", 45, LARGEUR, 6, prenom_tuteur))
    elements.append(_ligne("Téléphone :", 45, LARGEUR, 6, eleve.telephone_tuteur or ""))
    elements.append(_ligne("Profession :", 45, LARGEUR, 6, eleve.profession_tuteur or ""))
    elements.append(_ligne("Adresse :", 45, LARGEUR, 6, eleve.adresse_tuteur or ""))

    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph("Signature du parent de l'élève", signature_style))

    # =====================================================
    # Pied de page — Callback
    # =====================================================
    nom_complet = f"{_v(eleve.nom).upper()} {_v(eleve.prenom)}".strip()
    classe_txt = classe_nom or "—"
    annee_txt = annee_libelle or "—"

    def dessiner_pied(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(NOIR)
        canvas_obj.setLineWidth(0.5)

        largeur_page = A4[0]
        marge = 5 * mm
        y_bas = 6 * mm

        canvas_obj.line(marge, y_bas + 5 * mm, largeur_page - marge, y_bas + 5 * mm)

        canvas_obj.setFont('Helvetica-BoldOblique', 7.5)
        canvas_obj.setFillColor(NOIR)
        texte_pied = (
            f"Cette fiche fait preuve de l'inscription de l'élève "
            f"{nom_complet}, en classe de {classe_txt} "
            f"pour l'année scolaire {annee_txt}"
        )
        canvas_obj.drawCentredString(largeur_page / 2.0, y_bas, texte_pied)

        canvas_obj.restoreState()

    doc.onFirstPage = dessiner_pied
    doc.onLaterPages = dessiner_pied

    doc.build(elements)
    output.seek(0)
    return output
