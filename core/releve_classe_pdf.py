"""
ScolaEdu_AKEK — Relevé de notes de classe PDF (A4 paysage).
Session 2 : tableau récapitulatif de toutes les matières pour tous les élèves.
Version 1.
"""
from io import BytesIO
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)

from core.entete_document import generer_entete_document


# =====================================================
# COULEURS
# =====================================================
BLEU_MARINE = colors.HexColor('#1E3A8A')
BLEU_CLAIR  = colors.HexColor('#DBEAFE')
JAUNE       = colors.HexColor('#FCD34D')
GRIS_CLAIR  = colors.HexColor('#F1F5F9')
GRIS_TEXTE  = colors.HexColor('#64748B')
VERT        = colors.HexColor('#16A34A')
ROUGE       = colors.HexColor('#DC2626')


# =====================================================
# HELPERS
# =====================================================
def _fmt2(v):
    if v is None:
        return "—"
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)


def _fmt_rang(r):
    if r is None:
        return "—"
    return str(r)


def _appreciation(moy):
    if moy is None:
        return "—"
    m = float(moy)
    if m < 5:    return "Très faible"
    if m < 7:    return "Faible"
    if m < 9:    return "Insuffisant"
    if m < 10:   return "Passable"
    if m < 12:   return "Assez bien"
    if m < 14:   return "Bien"
    if m < 16:   return "Très bien"
    return "Excellent"


# =====================================================
# CALCUL DES DONNÉES
# =====================================================
def _calculer_releve(classe, trimestre):
    """
    Retourne un dict :
        matieres       : liste de MatiereClasse triés
        eleves_data    : liste de dicts par élève (notes par matière, moyenne, rang, appréciation)
        stats          : stats générales de la classe
    """
    from core.models import MatiereClasse, Note, Inscription, Eleve

    matieres_classe = list(
        MatiereClasse.objects.filter(classe=classe)
        .select_related('matiere', 'enseignant__user')
        .order_by('matiere__ordre', 'matiere__nom')
    )

    inscriptions = list(
        Inscription.objects.filter(classe=classe, actif=True)
        .select_related('eleve')
        .order_by('eleve__nom', 'eleve__prenom')
    )

    matieres_ids = [mc.matiere_id for mc in matieres_classe]

    # Récupérer toutes les notes en une seule requête
    notes_qs = Note.objects.filter(
        eleve__in=[i.eleve for i in inscriptions],
        matiere_id__in=matieres_ids,
        trimestre=trimestre,
    )
    notes_map = {}
    for n in notes_qs:
        notes_map[(n.eleve_id, n.matiere_id)] = n

    eleves_data = []

    for insc in inscriptions:
        eleve = insc.eleve
        notes_matieres = {}
        total_points = Decimal('0')
        somme_coefs = Decimal('0')

        for mc in matieres_classe:
            note = notes_map.get((eleve.id, mc.matiere_id))
            moy = note.moyenne_finale if note else None
            notes_matieres[mc.matiere_id] = moy

            if moy is not None:
                coef = Decimal(str(mc.coefficient))
                total_points += Decimal(str(moy)) * coef
                somme_coefs += coef

        moy_trim = None
        if somme_coefs > 0:
            moy_trim = round(float(total_points / somme_coefs), 2)

        eleves_data.append({
            'eleve': eleve,
            'classe': classe,
            'notes': notes_matieres,
            'moyenne': moy_trim,
            'rang': None,
            'appreciation': _appreciation(moy_trim),
        })

    # Calcul des rangs (avec gestion des ex-æquo)
    eleves_avec_moy = [e for e in eleves_data if e['moyenne'] is not None]
    eleves_avec_moy.sort(key=lambda x: -x['moyenne'])

    rang_courant = 0
    rang_reel = 0
    moy_prec = None
    for e in eleves_avec_moy:
        rang_reel += 1
        if e['moyenne'] != moy_prec:
            rang_courant = rang_reel
            moy_prec = e['moyenne']
        e['rang'] = rang_courant

    # Stats générales
    moyennes = [e['moyenne'] for e in eleves_data if e['moyenne'] is not None]
    stats = {
        'effectif': len(eleves_data),
        'effectif_notes': len(moyennes),
        'moyenne_classe': round(sum(moyennes) / len(moyennes), 2) if moyennes else None,
        'plus_forte': round(max(moyennes), 2) if moyennes else None,
        'plus_faible': round(min(moyennes), 2) if moyennes else None,
        'taux_reussite': round((sum(1 for m in moyennes if m >= 10) / len(moyennes)) * 100, 1) if moyennes else None,
        'nb_reussite': sum(1 for m in moyennes if m >= 10),
        'nb_echec': sum(1 for m in moyennes if m < 10),
    }

    # Stats par matière (moyenne de classe dans chaque matière)
    stats_matieres = {}
    for mc in matieres_classe:
        m_moyennes = []
        for e in eleves_data:
            v = e['notes'].get(mc.matiere_id)
            if v is not None:
                m_moyennes.append(float(v))
        if m_moyennes:
            stats_matieres[mc.matiere_id] = {
                'moyenne': round(sum(m_moyennes) / len(m_moyennes), 2),
                'plus_forte': round(max(m_moyennes), 2),
                'plus_faible': round(min(m_moyennes), 2),
            }
        else:
            stats_matieres[mc.matiere_id] = {
                'moyenne': None, 'plus_forte': None, 'plus_faible': None,
            }

    return {
        'matieres_classe': matieres_classe,
        'eleves_data': eleves_data,
        'stats': stats,
        'stats_matieres': stats_matieres,
    }


# =====================================================
# GÉNÉRATION PDF
# =====================================================
def exporter_releve_classe_pdf(classe, trimestre, config=None, utilisateur=None,
                                annee_libelle=None, etablissement=None):
    """
    Génère un PDF A4 paysage : relevé de notes de toute la classe pour un trimestre.
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
    elements.append(Spacer(1, 2 * mm))

    # ===== Titre =====
    titre_style = ParagraphStyle(
        'Titre', parent=styles['Normal'],
        fontSize=14, leading=16, alignment=1,
        textColor=colors.white, fontName='Helvetica-Bold',
    )
    sous_titre_style = ParagraphStyle(
        'SousTitre', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=1,
        textColor=colors.black, fontName='Helvetica-Bold',
    )
    info_style = ParagraphStyle(
        'Info', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=1,
        textColor=GRIS_TEXTE,
    )

    titre_bloc = Table(
        [[Paragraph("RELEVÉ DE NOTES DE LA CLASSE", titre_style)]],
        colWidths=[285 * mm],
        rowHeights=[9 * mm],
    )
    titre_bloc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(titre_bloc)

    sous_titre_bloc = Table(
        [[Paragraph(
            f"Classe : <b>{classe.nom}</b>  |  "
            f"{trimestre.get_numero_display()}  |  "
            f"Année scolaire : <b>{annee_libelle or '—'}</b>",
            sous_titre_style
        )]],
        colWidths=[285 * mm],
        rowHeights=[6 * mm],
    )
    sous_titre_bloc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), JAUNE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(sous_titre_bloc)
    elements.append(Spacer(1, 3 * mm))

    # ===== Calcul =====
    data = _calculer_releve(classe, trimestre)
    matieres_classe = data['matieres_classe']
    eleves_data = data['eleves_data']
    stats = data['stats']
    stats_matieres = data['stats_matieres']

    # ===== Styles de cellules =====
    cell_h = ParagraphStyle(
        'CH', parent=styles['Normal'],
        fontSize=6, leading=7, alignment=1,
        textColor=colors.white, fontName='Helvetica-Bold',
    )
    cell_h_rotate = ParagraphStyle(
        'CHR', parent=styles['Normal'],
        fontSize=6, leading=7, alignment=1,
        textColor=colors.white, fontName='Helvetica-Bold',
    )
    cell_b = ParagraphStyle(
        'CB', parent=styles['Normal'],
        fontSize=6.5, leading=8, alignment=0,
        textColor=colors.black, fontName='Helvetica-Bold',
    )
    cell_n = ParagraphStyle(
        'CN', parent=styles['Normal'],
        fontSize=6.5, leading=8, alignment=1,
        textColor=colors.black,
    )
    cell_bold = ParagraphStyle(
        'CBold', parent=styles['Normal'],
        fontSize=6.8, leading=8, alignment=1,
        textColor=colors.black, fontName='Helvetica-Bold',
    )
    cell_rouge = ParagraphStyle(
        'CR', parent=styles['Normal'],
        fontSize=6.8, leading=8, alignment=1,
        textColor=ROUGE, fontName='Helvetica-Bold',
    )
    cell_vert = ParagraphStyle(
        'CV', parent=styles['Normal'],
        fontSize=6.8, leading=8, alignment=1,
        textColor=VERT, fontName='Helvetica-Bold',
    )

    # ===== Construction du tableau =====
    # Colonnes fixes (largeur en cm)
    NB_MATIERES = len(matieres_classe)

    # On calcule la largeur disponible :
    # 285 mm - marge = ~283 mm
    # Colonnes fixes : N° (0.7) + Matricule (1.8) + Nom (3.5) + Moy (1.2) + Rang (0.9) + Appr (1.8) = 9.9 cm
    # Reste pour les matières
    largeur_fixe_cm = 0.7 + 1.8 + 3.5 + 1.2 + 0.9 + 1.8  # = 9.9
    largeur_totale_cm = 28.3
    largeur_dispo_matieres = largeur_totale_cm - largeur_fixe_cm

    if NB_MATIERES > 0:
        largeur_matiere_cm = max(0.9, min(1.6, largeur_dispo_matieres / NB_MATIERES))
    else:
        largeur_matiere_cm = 1.2

    # En-tête ligne 1 : N° | Matricule | Nom | (matières...) | Moy | Rang | Appréciation
    header1 = [
        Paragraph("N°", cell_h),
        Paragraph("Matricule", cell_h),
        Paragraph("Nom et Prénom(s)", cell_h),
    ]
    for mc in matieres_classe:
        header1.append(Paragraph(mc.matiere.code or mc.matiere.nom[:6], cell_h))
    header1 += [
        Paragraph("Moy", cell_h),
        Paragraph("Rang", cell_h),
        Paragraph("Appréciation", cell_h),
    ]

    # En-tête ligne 2 : vide | vide | vide | coefficients... | /20 | / | 
    header2 = [
        Paragraph("", cell_h),
        Paragraph("", cell_h),
        Paragraph("Coef. →", cell_h),
    ]
    for mc in matieres_classe:
        header2.append(Paragraph(str(mc.coefficient), cell_h))
    header2 += [
        Paragraph("/20", cell_h),
        Paragraph("/", cell_h),
        Paragraph("", cell_h),
    ]

    table_data = [header1, header2]

    for idx, e in enumerate(eleves_data, start=1):
        ligne = [
            Paragraph(str(idx), cell_n),
            Paragraph(e['eleve'].matricule or "—", cell_n),
            Paragraph(f"{e['eleve'].nom.upper()} {e['eleve'].prenom}", cell_b),
        ]
        for mc in matieres_classe:
            v = e['notes'].get(mc.matiere_id)
            ligne.append(Paragraph(_fmt2(v), cell_bold if v is not None else cell_n))
        # Moyenne
        moy = e['moyenne']
        if moy is None:
            ligne.append(Paragraph("—", cell_n))
        elif moy >= 10:
            ligne.append(Paragraph(_fmt2(moy), cell_vert))
        else:
            ligne.append(Paragraph(_fmt2(moy), cell_rouge))
        # Rang
        ligne.append(Paragraph(_fmt_rang(e['rang']), cell_bold))
        # Appréciation
        ligne.append(Paragraph(e['appreciation'], cell_n))
        table_data.append(ligne)

    # Ligne des stats de classe
    ligne_stats = [
        Paragraph("", cell_n),
        Paragraph("", cell_n),
        Paragraph("Moy. classe", cell_b),
    ]
    for mc in matieres_classe:
        sm = stats_matieres.get(mc.matiere_id, {})
        ligne_stats.append(Paragraph(_fmt2(sm.get('moyenne')), cell_bold))
    ligne_stats += [
        Paragraph(_fmt2(stats.get('moyenne_classe')), cell_bold),
        Paragraph("—", cell_n),
        Paragraph("", cell_n),
    ]
    table_data.append(ligne_stats)

    # Ligne plus forte
    ligne_forte = [
        Paragraph("", cell_n),
        Paragraph("", cell_n),
        Paragraph("Plus forte", cell_b),
    ]
    for mc in matieres_classe:
        sm = stats_matieres.get(mc.matiere_id, {})
        ligne_forte.append(Paragraph(_fmt2(sm.get('plus_forte')), cell_bold))
    ligne_forte += [
        Paragraph(_fmt2(stats.get('plus_forte')), cell_bold),
        Paragraph("—", cell_n),
        Paragraph("", cell_n),
    ]
    table_data.append(ligne_forte)

    # Ligne plus faible
    ligne_faible = [
        Paragraph("", cell_n),
        Paragraph("", cell_n),
        Paragraph("Plus faible", cell_b),
    ]
    for mc in matieres_classe:
        sm = stats_matieres.get(mc.matiere_id, {})
        ligne_faible.append(Paragraph(_fmt2(sm.get('plus_faible')), cell_bold))
    ligne_faible += [
        Paragraph(_fmt2(stats.get('plus_faible')), cell_bold),
        Paragraph("—", cell_n),
        Paragraph("", cell_n),
    ]
    table_data.append(ligne_faible)

    # Largeurs des colonnes
    col_widths = [
        0.7 * cm,   # N°
        1.8 * cm,   # Matricule
        3.5 * cm,   # Nom
    ]
    col_widths += [largeur_matiere_cm * cm] * NB_MATIERES
    col_widths += [
        1.2 * cm,   # Moy
        0.9 * cm,   # Rang
        1.8 * cm,   # Appréciation
    ]

    tbl = Table(table_data, colWidths=col_widths, repeatRows=2)
    tbl.setStyle(TableStyle([
        # En-tête
        ('BACKGROUND', (0, 0), (-1, 1), BLEU_MARINE),
        ('TEXTCOLOR', (0, 0), (-1, 1), colors.white),
        ('FONTNAME', (0, 0), (-1, 1), 'Helvetica-Bold'),
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, 1), 'MIDDLE'),
        # Corps
        ('VALIGN', (0, 2), (-1, -4), 'MIDDLE'),
        ('ALIGN', (0, 2), (0, -1), 'CENTER'),   # N°
        ('ALIGN', (1, 2), (1, -1), 'CENTER'),   # Matricule
        ('GRID', (0, 0), (-1, -4), 0.3, colors.HexColor('#CBD5E1')),
        ('BOX', (0, 0), (-1, -4), 1, BLEU_MARINE),
        # Lignes de stats
        ('BACKGROUND', (0, -3), (-1, -3), colors.HexColor('#E0E7FF')),
        ('BACKGROUND', (0, -2), (-1, -2), colors.HexColor('#DCFCE7')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FEE2E2')),
        ('BOX', (0, -3), (-1, -1), 1, BLEU_MARINE),
        ('GRID', (0, -3), (-1, -1), 0.3, colors.HexColor('#CBD5E1')),
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 1.5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1.5),
    ]))

    elements.append(tbl)
    elements.append(Spacer(1, 3 * mm))

    # ===== Statistiques générales =====
    stat_style = ParagraphStyle(
        'Stat', parent=styles['Normal'],
        fontSize=8, leading=10, alignment=0,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )
    stats_html = (
        f"<b>Effectif :</b> {stats['effectif']} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Élèves notés :</b> {stats['effectif_notes']} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Moyenne de la classe :</b> {_fmt2(stats['moyenne_classe'])} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Plus forte :</b> {_fmt2(stats['plus_forte'])} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Plus faible :</b> {_fmt2(stats['plus_faible'])} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<b>Taux de réussite (≥10) :</b> {stats['taux_reussite']}% "
        f"({stats['nb_reussite']} réussites / {stats['nb_echec']} échecs)"
    )
    elements.append(Paragraph(stats_html, stat_style))
    elements.append(Spacer(1, 5 * mm))

    # ===== Signature du chef =====
    nom_chef = ""
    titre_chef = ""
    ville = "—"
    if config:
        nom_chef = config.nom_chef or ""
        titre_chef = config.titre_chef or ""
        ville = (config.ville_document or "").strip() or (config.commune or "").strip() or "—"

    date_sign = datetime.now().strftime('%d/%m/%Y')

    signature_style = ParagraphStyle(
        'Signature', parent=styles['Normal'],
        fontSize=9, leading=11, alignment=2,
        textColor=colors.black,
    )
    nom_chef_style = ParagraphStyle(
        'NomChef', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=2,
        textColor=colors.black, fontName='Helvetica-Bold',
    )

    sign_data = [[
        Paragraph(f"Fait à <b>{ville}</b>, le <b>{date_sign}</b>", signature_style),
    ], [
        Paragraph(f"<b>{nom_chef.upper()}</b>", nom_chef_style),
    ], [
        Paragraph(f"<i>{titre_chef}</i>", ParagraphStyle(
            'TCh', parent=styles['Normal'],
            fontSize=8, leading=10, alignment=2,
            textColor=GRIS_TEXTE,
        )),
    ]]

    sign_tbl = Table(sign_data, colWidths=[283 * mm])
    sign_tbl.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(sign_tbl)
    elements.append(Spacer(1, 2 * mm))

    # Pied de page
    pied_style = ParagraphStyle(
        'Pied', parent=styles['Normal'],
        fontSize=7, leading=9, alignment=1,
        textColor=GRIS_TEXTE, fontName='Helvetica-Oblique',
    )
    pied_txt = f"Relevé généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    if utilisateur:
        nom_util = utilisateur.get_full_name() or utilisateur.username
        pied_txt += f" par {nom_util}"
    elements.append(Paragraph(pied_txt, pied_style))

    doc.build(elements)
    output.seek(0)
    return output
