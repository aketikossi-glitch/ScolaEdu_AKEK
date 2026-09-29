"""
ScolaEdu_AKEK — Fiche pré-remplie d'inscription (PDF A4 portrait).
Version 4 :
  - Découpage Nom/Prénoms (parents + tuteur)
  - Cases pré-cochées (Nouveau/Redoublant, Sexe, Cycle)
  - Texte en gras Caveat-Bold
  - Bleu Bic (#0000B3)
  - En-tête mutualisé via core.entete_document.generer_entete_document
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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from django.conf import settings

from core.entete_document import generer_entete_document


# ===== Enregistrer les polices manuscrites Caveat =====
POLICE_MANUSCRITE = 'Helvetica-Bold'      # fallback
POLICE_MANUSCRITE_BOLD = 'Helvetica-Bold'
try:
    path_reg = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Caveat-Regular.ttf')
    path_bold = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Caveat-Bold.ttf')

    if os.path.exists(path_reg):
        pdfmetrics.registerFont(TTFont('Caveat', path_reg))
        POLICE_MANUSCRITE = 'Caveat'

    if os.path.exists(path_bold):
        pdfmetrics.registerFont(TTFont('Caveat-Bold', path_bold))
        POLICE_MANUSCRITE_BOLD = 'Caveat-Bold'
    else:
        POLICE_MANUSCRITE_BOLD = POLICE_MANUSCRITE
except Exception:
    pass

NOIR = colors.HexColor('#000000')
BLEU_PUR = colors.HexColor('#0000B3')


# =====================================================
# HELPERS
# =====================================================
def _split_nom_prenoms(nom_complet):
    """Sépare 'KOSSI Afio' en ('KOSSI', 'Afio')."""
    if not nom_complet:
        return ('', '')
    parts = nom_complet.strip().split(' ', 1)
    if len(parts) == 1:
        return (parts[0], '')
    return (parts[0], parts[1])


# =====================================================
# CASE À COCHER
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
    """Case cochée avec une croix en Caveat-Bold bleu."""
    st = ParagraphStyle(
        'X', fontSize=10, leading=11, alignment=1,
        textColor=BLEU_PUR, fontName=POLICE_MANUSCRITE_BOLD,
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
# LIGNE AVEC VALEUR MANUSCRITE GRASSE BLEUE
# =====================================================
def _ligne(label, largeur_label_mm, largeur_totale_mm=200, hauteur_mm=6,
           valeur=""):
    styles = getSampleStyleSheet()
    st_label = ParagraphStyle(
        'LBL', parent=styles['Normal'],
        fontSize=9.5, leading=11.5,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    st_valeur = ParagraphStyle(
        'VAL', parent=styles['Normal'],
        fontSize=11, leading=13,
        textColor=BLEU_PUR, fontName=POLICE_MANUSCRITE_BOLD,
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
# OPTION AVEC CASE
# =====================================================
def _option_avec_case(texte, coche=False):
    styles = getSampleStyleSheet()
    st = ParagraphStyle(
        'OptTxt', parent=styles['Normal'],
        fontSize=9, leading=11, textColor=NOIR,
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
# LIGNE CODE ÉTABLISSEMENT
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
        fontSize=11, leading=13,
        textColor=BLEU_PUR, alignment=1,
        fontName=POLICE_MANUSCRITE_BOLD,
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
        fontSize=11, leading=13, textColor=BLEU_PUR,
        fontName=POLICE_MANUSCRITE_BOLD,
    )
    st_b = ParagraphStyle(
        'NivB', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR, fontName='Helvetica-Bold',
    )

    ligne = [
        Paragraph("<b>Niveau ¹ :</b>", st_b),
        Paragraph(niveau or "......................", st),
        Paragraph("<b>Classe ² :</b>", st_b),
        Paragraph(classe or "......................", st),
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
        fontSize=11, leading=13, textColor=BLEU_PUR,
        fontName=POLICE_MANUSCRITE_BOLD,
    )
    st_b = ParagraphStyle(
        'DSB', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR, fontName='Helvetica-Bold',
    )

    ligne = [
        Paragraph("<b>Date de Naissance :</b>", st_b),
        Paragraph(date_naiss or "....../....../................", st),
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
# BLOC HANDICAP
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
def exporter_fiche_preremplie_pdf(eleve, config=None, utilisateur=None,
                                   annee_courante=None):
    """Génère une fiche PRÉ-REMPLIE (format togolais)."""
    from core.models import Inscription

    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=0.5 * cm, rightMargin=0.5 * cm,
        topMargin=0.5 * cm, bottomMargin=0.5 * cm,
    )

    elements = []
    styles = getSampleStyleSheet()
    LARGEUR = 200

    # ===== Données =====
    etab = eleve.etablissement
    annee_libelle = annee_courante or ""
    inscription = Inscription.objects.filter(
        eleve=eleve, actif=True
    ).select_related('classe').first()
    classe_nom = inscription.classe.nom if inscription and inscription.classe else ""
    niveau_nom = inscription.classe.get_niveau_display() if inscription and inscription.classe else ""

    # Sexe
    est_masculin = eleve.sexe == 'M'
    est_feminin = eleve.sexe == 'F'

    # Statut
    est_nouveau = eleve.statut == 'nouveau'
    est_redoublant = eleve.statut == 'redoublant'

    # Date naissance au format JJ/MM/AAAA
    date_naiss_txt = ""
    if eleve.date_naissance:
        try:
            date_naiss_txt = eleve.date_naissance.strftime('%d/%m/%Y')
        except Exception:
            date_naiss_txt = str(eleve.date_naissance)

    # Infos établissement (depuis config)
    direction_reg = (config.direction_regionale if config else "") or ""
    inspection = (config.inspection if config else "") or ""
    perimetre = (config.perimetre_pedagogique if config else "") or ""
    commune_admin = (config.commune_administration if config else "") or ""
    nom_etab = etab.nom or ""
    code_etab = etab.code or ""

    # Cycle selon type_etablissement
    type_etab = (etab.type_etablissement or "").lower()
    cycle_prescolaire = (type_etab == 'maternelle')
    cycle_primaire = (type_etab == 'primaire')
    cycle_sec1 = (type_etab in ('college', 'complexe'))
    cycle_sec2 = (type_etab in ('lycee', 'complexe'))

    # ===== En-tête (mutualisé) =====
    elements.extend(generer_entete_document(
        config, style='complet', orientation='portrait'
    ))
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

    # ===== Titre principal =====
    titre_cell = Table(
        [[Paragraph("FICHE UNIQUE D'INSCRIPTION D'UN ÉLÈVE", titre_style)]],
        colWidths=[None],
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

    elements.append(_ligne("Direction Régionale :", 45, LARGEUR, valeur=direction_reg))
    elements.append(_ligne("Inspection :", 45, LARGEUR, valeur=inspection))
    elements.append(_ligne("Périmètre Pédagogique :", 45, LARGEUR, valeur=perimetre))
    elements.append(_ligne("Commune :", 45, LARGEUR, valeur=commune_admin))
    elements.append(_ligne("Etablissement :", 45, LARGEUR, valeur=nom_etab))
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
        "2- <b><u>Informations sur l'élève</u></b>",
        section_style
    ))

    elements.append(_ligne_niveau(
        niveau=niveau_nom, classe=classe_nom,
        est_nouveau=est_nouveau, est_redoublant=est_redoublant,
        largeur_totale_mm=LARGEUR
    ))
    elements.append(_ligne("Nom :", 18, LARGEUR, valeur=(eleve.nom or "").upper()))
    elements.append(_ligne("Prénoms :", 22, LARGEUR, valeur=eleve.prenom or ""))
    elements.append(_ligne_date_sexe(
        date_naiss=date_naiss_txt,
        est_masculin=est_masculin, est_feminin=est_feminin,
        largeur_totale_mm=LARGEUR
    ))
    elements.append(_ligne("Lieu de Naissance :", 38, LARGEUR,
                            valeur=eleve.lieu_naissance or ""))

    elements.append(_ligne_options(
        "Situation Famille de l'élève :",
        [("Parents Vivants", False), ("Orphelin", False),
         ("Orphelin Mère", False), ("Orphelin Père", False)],
        largeur_label_mm=50, largeur_totale_mm=LARGEUR
    ))

    elements.append(_ligne("Adresse Elève :", 30, LARGEUR,
                            valeur=eleve.adresse or ""))
    elements.append(_ligne("Préfecture de Naissance ³ :", 52, LARGEUR,
                            valeur=eleve.get_prefecture_naissance_display() or ""))
    elements.append(_ligne("Pays de Naissance :", 38, LARGEUR,
                            valeur=eleve.nationalite or ""))

    elements.append(_bloc_handicap(LARGEUR))
    elements.append(Spacer(1, 2 * mm))

    # =====================================================
    # SECTION 3 — PARENTS (avec découpage Nom/Prénoms)
    # =====================================================
    elements.append(Paragraph(
        "3- <b><u>Informations sur les parents de l'élève</u></b>",
        section_style
    ))

    st_cell_val = ParagraphStyle(
        'CellVal', parent=styles['Normal'],
        fontSize=11, leading=13, textColor=BLEU_PUR,
        fontName=POLICE_MANUSCRITE_BOLD,
    )
    st_cell_label = ParagraphStyle(
        'CellLabel', parent=styles['Normal'],
        fontSize=9.5, leading=11.5, textColor=NOIR, fontName='Helvetica-Bold',
    )
    st_header = ParagraphStyle(
        'Hdr', parent=styles['Normal'],
        fontSize=10, leading=12, textColor=NOIR,
        alignment=1, fontName='Helvetica-Oblique',
    )

    # Découpage
    nom_pere, prenom_pere = _split_nom_prenoms(eleve.nom_pere)
    nom_mere, prenom_mere = _split_nom_prenoms(eleve.nom_mere)

    header_parents = [
        Paragraph("", styles['Normal']),
        Paragraph("<i>Père</i>", st_header),
        Paragraph("<i>Mère</i>", st_header),
    ]
    parents_data = [
        [Paragraph("<b>Nom</b>", st_cell_label),
         Paragraph(nom_pere, st_cell_val),
         Paragraph(nom_mere, st_cell_val)],
        [Paragraph("<b>Prénoms</b>", st_cell_label),
         Paragraph(prenom_pere, st_cell_val),
         Paragraph(prenom_mere, st_cell_val)],
        [Paragraph("<b>Téléphone</b>", st_cell_label),
         Paragraph(eleve.telephone_pere or "", st_cell_val),
         Paragraph(eleve.telephone_mere or "", st_cell_val)],
        [Paragraph("<b>Profession ⁴</b>", st_cell_label),
         Paragraph(eleve.profession_pere or "", st_cell_val),
         Paragraph(eleve.profession_mere or "", st_cell_val)],
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
    # SECTION 4 — TUTEUR (avec découpage Nom/Prénoms)
    # =====================================================
    elements.append(Paragraph(
        "4- <b><u>Personne à prévenir en cas d'urgence pour l'élève (Tuteur)</u></b>",
        section_style
    ))

    nom_tuteur, prenom_tuteur = _split_nom_prenoms(eleve.nom_tuteur)

    elements.append(_ligne("Nom :", 18, LARGEUR, valeur=nom_tuteur))
    elements.append(_ligne("Prénoms :", 22, LARGEUR, valeur=prenom_tuteur))
    elements.append(_ligne("Téléphone :", 25, LARGEUR,
                            valeur=eleve.telephone_tuteur or ""))
    elements.append(_ligne("Profession :", 25, LARGEUR,
                            valeur=eleve.profession_tuteur or ""))
    elements.append(_ligne("Adresse :", 22, LARGEUR,
                            valeur=eleve.adresse_tuteur or ""))

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
