"""
ScolaEdu_AKEK — Liste des élèves d'une classe PDF (A4 paysage).
Session 17 : liste nominative + statistiques démographiques.
Version 2 : titres sobres (sans bandeaux), en-tête + total grisés,
            signature et pied de page retirés.
"""
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

from core.entete_document import generer_entete_document


# =====================================================
# COULEURS
# =====================================================
BLEU_MARINE  = colors.HexColor('#1E3A8A')
GRIS_ENTETE  = colors.HexColor('#E5E7EB')   # gris clair (en-tête + total)
GRIS_LIGNE   = colors.HexColor('#F8FAFC')   # gris très clair (alternance)
GRIS_TEXTE   = colors.HexColor('#64748B')
GRIS_SOMBRE  = colors.HexColor('#1F2937')   # gris foncé pour les titres
NOIR         = colors.HexColor('#000000')


# =====================================================
# HELPERS
# =====================================================
def _fmt_date(d):
    if not d:
        return "—"
    try:
        return d.strftime('%d/%m/%Y')
    except Exception:
        return str(d)


def _age(d):
    if not d:
        return "—"
    from datetime import date
    today = date.today()
    try:
        return str(today.year - d.year - ((today.month, today.day) < (d.month, d.day)))
    except Exception:
        return "—"


def _statut_display(eleve):
    mapping = {
        'nouveau': 'Nouveau',
        'redoublant': 'Redoublant',
        'transfere': 'Transféré',
    }
    return mapping.get(eleve.statut, '—')


def _calculer_liste(classe):
    """
    Retourne un dict :
      eleves_data : liste de dicts triés (Nom, Prénom)
      stats       : effectif total, garçons, filles
    """
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
            'eleve': eleve,
            'matricule': eleve.matricule or '—',
            'nom': (eleve.nom or '').upper(),
            'prenom': eleve.prenom or '',
            'sexe': eleve.get_sexe_display() if hasattr(eleve, 'get_sexe_display') else eleve.sexe,
            'sexe_code': eleve.sexe,
            'date_naiss': _fmt_date(eleve.date_naissance),
            'age': _age(eleve.date_naissance),
            'lieu_naiss': eleve.lieu_naissance or '—',
            'statut': _statut_display(eleve),
        })

    nb_garcons = sum(1 for e in eleves_data if e['sexe_code'] == 'M')
    nb_filles = sum(1 for e in eleves_data if e['sexe_code'] == 'F')

    stats = {
        'effectif': len(eleves_data),
        'garcons': nb_garcons,
        'filles': nb_filles,
    }
    return {
        'eleves_data': eleves_data,
        'stats': stats,
    }


# =====================================================
# GÉNÉRATION PDF
# =====================================================
def exporter_liste_classe_pdf(classe, config=None, utilisateur=None,
                              annee_libelle=None, etablissement=None):
    """
    Génère un PDF A4 paysage : liste nominative des élèves d'une classe.
    """
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4),
        leftMargin=6 * mm, rightMargin=6 * mm,
        topMargin=6 * mm, bottomMargin=8 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    # ===== En-tête officiel =====
    elements.extend(generer_entete_document(config, style='complet', orientation='paysage'))
    elements.append(Spacer(1, 3 * mm))

    # ===== Styles des titres (sobres, sans fond) =====
    titre_style = ParagraphStyle(
        'Titre', parent=styles['Normal'],
        fontSize=14, leading=16, alignment=1,
        textColor=GRIS_SOMBRE, fontName='Helvetica-Bold',
    )
    sous_titre_style = ParagraphStyle(
        'SousTitre', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=1,
        textColor=GRIS_SOMBRE, fontName='Helvetica-Bold',
    )

    # ===== Titre principal (texte seul, centré) =====
    elements.append(Paragraph("LISTE DES ÉLÈVES DE LA CLASSE", titre_style))
    elements.append(Spacer(1, 1 * mm))

    # ===== Sous-titre (texte seul, centré) =====
    niveau_display = classe.get_niveau_display() if hasattr(classe, 'get_niveau_display') else classe.niveau
    sous_titre_txt = (
        f"Classe : <b>{classe.nom}</b>  |  "
        f"Niveau : <b>{niveau_display}</b>  |  "
        f"Année scolaire : <b>{annee_libelle or '—'}</b>"
    )
    elements.append(Paragraph(sous_titre_txt, sous_titre_style))
    elements.append(Spacer(1, 3 * mm))

    # ===== Calcul des données =====
    data = _calculer_liste(classe)
    eleves_data = data['eleves_data']
    stats = data['stats']

    # ===== Styles des cellules =====
    cell_h = ParagraphStyle(
        'CH', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=1,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    cell_b = ParagraphStyle(
        'CB', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=0,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    cell_n = ParagraphStyle(
        'CN', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=1,
        textColor=NOIR,
    )
    cell_n_left = ParagraphStyle(
        'CNL', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=0,
        textColor=NOIR,
    )
    cell_total = ParagraphStyle(
        'CT', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=0,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    cell_total_center = ParagraphStyle(
        'CTC', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=1,
        textColor=NOIR, fontName='Helvetica-Bold',
    )

    # ===== En-tête du tableau =====
    header = [
        Paragraph("N°", cell_h),
        Paragraph("Matricule", cell_h),
        Paragraph("Nom", cell_h),
        Paragraph("Prénoms", cell_h),
        Paragraph("Sexe", cell_h),
        Paragraph("Date de naissance", cell_h),
        Paragraph("Âge", cell_h),
        Paragraph("Lieu de naissance", cell_h),
        Paragraph("Statut", cell_h),
    ]
    table_data = [header]

    # ===== Lignes élèves =====
    for idx, e in enumerate(eleves_data, start=1):
        ligne = [
            Paragraph(str(idx), cell_n),
            Paragraph(e['matricule'], cell_n),
            Paragraph(e['nom'], cell_b),
            Paragraph(e['prenom'], cell_n_left),
            Paragraph(e['sexe'], cell_n),
            Paragraph(e['date_naiss'], cell_n),
            Paragraph(e['age'], cell_n),
            Paragraph(e['lieu_naiss'], cell_n_left),
            Paragraph(e['statut'], cell_n),
        ]
        table_data.append(ligne)

    # ===== Ligne TOTAL =====
    ligne_total = [
        Paragraph("", cell_n),
        Paragraph("", cell_n),
        Paragraph(f"TOTAL : {stats['effectif']} élève(s)", cell_total),
        Paragraph("", cell_n_left),
        Paragraph(f"{stats['garcons']} G / {stats['filles']} F", cell_total_center),
        Paragraph("", cell_n),
        Paragraph("", cell_n),
        Paragraph("", cell_n_left),
        Paragraph("", cell_n),
    ]
    table_data.append(ligne_total)

    # ===== Largeurs des colonnes (total = 285 mm) =====
    col_widths = [
        1.0 * cm,   # N°
        2.5 * cm,   # Matricule
        5.0 * cm,   # Nom
        5.0 * cm,   # Prénoms
        1.8 * cm,   # Sexe
        3.2 * cm,   # Date naiss.
        1.5 * cm,   # Âge
        4.5 * cm,   # Lieu naiss.
        3.0 * cm,   # Statut
    ]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # En-tête : fond gris, texte noir gras
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE),
        ('TEXTCOLOR', (0, 0), (-1, 0), NOIR),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
        # Corps
        ('VALIGN', (0, 1), (-1, -2), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.3, colors.HexColor('#CBD5E1')),
        ('BOX', (0, 0), (-1, -2), 0.6, NOIR),
        # Alternance de lignes (gris très clair sur pairs)
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, GRIS_LIGNE]),
        # Ligne TOTAL : fond gris, texte noir gras
        ('BACKGROUND', (0, -1), (-1, -1), GRIS_ENTETE),
        ('BOX', (0, -1), (-1, -1), 0.6, NOIR),
        ('GRID', (0, -1), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(tbl)

    doc.build(elements)
    output.seek(0)
    return output
