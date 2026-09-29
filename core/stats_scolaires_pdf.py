"""
ScolaEdu_AKEK — Statistiques scolaires PDF.
Page 1 : Analyse par matière (notes de composition) + stats globales.
Format A4 paysage, 4 colonnes de matières.
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
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

from core.entete_document import generer_entete_document


# =====================================================
# COULEURS
# =====================================================
BLEU_MARINE = colors.HexColor('#1E3A8A')
BLEU_CLAIR  = colors.HexColor('#DBEAFE')
JAUNE       = colors.HexColor('#FCD34D')
GRIS_CLAIR  = colors.HexColor('#F1F5F9')
GRIS_BORD   = colors.HexColor('#CBD5E1')
GRIS_TEXTE  = colors.HexColor('#64748B')
VERT        = colors.HexColor('#16A34A')
ROUGE       = colors.HexColor('#DC2626')
BLEU_G      = colors.HexColor('#2563EB')  # Garçons
ROSE_F      = colors.HexColor('#DB2777')  # Filles


# =====================================================
# HELPERS
# =====================================================
def _fmt2(v):
    if v is None:
        return "0.00"
    try:
        return f"{float(v):.2f}"
    except Exception:
        return "0.00"


def _fmt_pct(n, total):
    if total == 0:
        return "0.00%"
    return f"{(n / total * 100):.2f}%"


def _tranche(v):
    """Retourne l'index de la tranche pour une note (0-3)."""
    if v is None:
        return None
    try:
        f = float(v)
    except Exception:
        return None
    if f < 6:    return 0
    if f < 10:   return 1
    if f < 15:   return 2
    return 3


# =====================================================
# CALCUL DES STATS
# =====================================================
def _calculer_stats_matiere(classe, trimestre, matiere_classe):
    """
    Retourne les stats pour UNE matière dans UNE classe :
    - effectif par sexe
    - nombres par tranche (0-3) par sexe
    - moyenne par sexe
    """
    from core.models import Note, Inscription

    inscriptions = Inscription.objects.filter(
        classe=classe, actif=True
    ).select_related('eleve')

    eleves = [i.eleve for i in inscriptions]
    total_g = sum(1 for e in eleves if e.sexe == 'M')
    total_f = sum(1 for e in eleves if e.sexe == 'F')

    tranches = {
        'G': [0, 0, 0, 0],
        'F': [0, 0, 0, 0],
        'T': [0, 0, 0, 0],
    }

    notes = Note.objects.filter(
        eleve__in=eleves,
        matiere=matiere_classe.matiere,
        trimestre=trimestre,
    ).select_related('eleve')

    somme_g = Decimal('0')
    somme_f = Decimal('0')
    nb_g = 0
    nb_f = 0

    for n in notes:
        moy = n.moyenne_finale
        if moy is None:
            continue
        t = _tranche(moy)
        if t is None:
            continue

        sexe = n.eleve.sexe
        if sexe == 'M':
            tranches['G'][t] += 1
            tranches['T'][t] += 1
            somme_g += Decimal(str(moy))
            nb_g += 1
        elif sexe == 'F':
            tranches['F'][t] += 1
            tranches['T'][t] += 1
            somme_f += Decimal(str(moy))
            nb_f += 1

    moy_g = round(float(somme_g / nb_g), 2) if nb_g > 0 else None
    moy_f = round(float(somme_f / nb_f), 2) if nb_f > 0 else None
    nb_t = nb_g + nb_f
    moy_t = None
    if nb_t > 0:
        moy_t = round(float((somme_g + somme_f) / nb_t), 2)

    return {
        'total_g': total_g,
        'total_f': total_f,
        'tranches': tranches,
        'moy_g': moy_g,
        'moy_f': moy_f,
        'moy_t': moy_t,
        'nb_g': nb_g,
        'nb_f': nb_f,
        'nb_t': nb_t,
    }


def _calculer_stats_globales(classe, trimestre):
    """
    Stats globales de la classe pour le trimestre :
    - Effectifs par sexe
    - Présents (élèves ayant au moins 1 note)
    - Moyennes >= 10 (par sexe + total)
    """
    from core.models import Note, Inscription, MatiereClasse

    inscriptions = Inscription.objects.filter(
        classe=classe, actif=True
    ).select_related('eleve')
    eleves = [i.eleve for i in inscriptions]

    total_g = sum(1 for e in eleves if e.sexe == 'M')
    total_f = sum(1 for e in eleves if e.sexe == 'F')

    matieres_ids = list(
        MatiereClasse.objects.filter(classe=classe)
        .values_list('matiere_id', flat=True)
    )

    # Notes par élève
    notes_qs = Note.objects.filter(
        eleve__in=eleves,
        matiere_id__in=matieres_ids,
        trimestre=trimestre,
    )

    notes_par_eleve = {}
    for n in notes_qs:
        notes_par_eleve.setdefault(n.eleve_id, []).append(n)

    presents_g = 0
    presents_f = 0
    moy_ok_g = 0
    moy_ok_f = 0

    for eleve in eleves:
        notes = notes_par_eleve.get(eleve.id, [])
        # Élève présent = au moins une note non-nulle
        a_notes = any(n.moyenne_finale is not None for n in notes)

        if a_notes:
            if eleve.sexe == 'M':
                presents_g += 1
            elif eleve.sexe == 'F':
                presents_f += 1

        # Calcul de la moyenne de l'élève
        total_pts = Decimal('0')
        coef_sum = Decimal('0')
        for n in notes:
            if n.moyenne_finale is None:
                continue
            try:
                coef = n.matiere.classes.get(classe=classe).coefficient
            except Exception:
                coef = 1
            total_pts += Decimal(str(n.moyenne_finale)) * Decimal(str(coef))
            coef_sum += Decimal(str(coef))

        if coef_sum > 0:
            moy_eleve = float(total_pts / coef_sum)
            if moy_eleve >= 10:
                if eleve.sexe == 'M':
                    moy_ok_g += 1
                elif eleve.sexe == 'F':
                    moy_ok_f += 1

    return {
        'inscrits_g': total_g,
        'inscrits_f': total_f,
        'inscrits_t': total_g + total_f,
        'presents_g': presents_g,
        'presents_f': presents_f,
        'presents_t': presents_g + presents_f,
        'moy_ok_g': moy_ok_g,
        'moy_ok_f': moy_ok_f,
        'moy_ok_t': moy_ok_g + moy_ok_f,
    }


# =====================================================
# GÉNÉRATION PDF
# =====================================================
def exporter_stats_composition_pdf(classe, trimestre, config=None, utilisateur=None,
                                     annee_libelle=None):
    """
    Page 1 des statistiques : analyse par matière + stats globales.
    """
    from core.models import MatiereClasse

    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4),
        leftMargin=6 * mm, rightMargin=6 * mm,
        topMargin=3 * mm, bottomMargin=4 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    # ===== En-tête officiel =====
    elements.extend(generer_entete_document(config, style='complet', orientation='paysage'))
    elements.append(Spacer(1, 2 * mm))

    # ===== Titre principal =====
    titre_style = ParagraphStyle(
        'Titre', parent=styles['Normal'],
        fontSize=13, leading=15, alignment=1,
        textColor=colors.white, fontName='Helvetica-Bold',
    )
    sous_titre_style = ParagraphStyle(
        'SousTitre', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=1,
        textColor=colors.black, fontName='Helvetica-Bold',
    )
    section_style = ParagraphStyle(
        'Section', parent=styles['Normal'],
        fontSize=11, leading=13, alignment=1,
        textColor=colors.white, fontName='Helvetica-Bold',
    )
    # ✅ Style section visible (texte bleu marine, sans fond) — Session 19b
    section_style_visible = ParagraphStyle(
        'SecVisible', parent=styles['Normal'],
        fontSize=11, leading=13, alignment=1,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )
    sous_section_style = ParagraphStyle(
        'SousSection', parent=styles['Normal'],
        fontSize=9, leading=11, alignment=1,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )
    # ✅ Session 19c — Styles Page 1 (titres visibles sans fond)
    titre_style_p1 = ParagraphStyle(
        'TitreP1', parent=styles['Normal'],
        fontSize=14, leading=16, alignment=1,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )
    sous_titre_style_p1 = ParagraphStyle(
        'SousTitreP1', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=1,
        textColor=colors.HexColor('#1F2937'), fontName='Helvetica-Bold',
    )

    titre = Table(
        [[Paragraph("ANALYSE PAR MATIÈRE — NOTES DE COMPOSITION", titre_style_p1)]],
        colWidths=[285 * mm],
        rowHeights=[8 * mm],
    )
    titre.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(titre)

    sous_titre = Table(
        [[Paragraph(
            f"Classe : <b>{classe.nom}</b>  |  "
            f"{trimestre.get_numero_display()}  |  "
            f"Année scolaire : <b>{annee_libelle or '—'}</b>",
            sous_titre_style_p1
        )]],
        colWidths=[285 * mm],
        rowHeights=[6 * mm],
    )
    sous_titre.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(sous_titre)
    elements.append(Spacer(1, 1.5 * mm))

    # ===== Récupérer les matières =====
    matieres_classe = list(
        MatiereClasse.objects.filter(classe=classe)
        .select_related('matiere')
        .order_by('matiere__ordre', 'matiere__nom')
    )

    if not matieres_classe:
        elements.append(Paragraph(
            "Aucune matière affectée à cette classe.",
            ParagraphStyle('Vide', parent=styles['Normal'],
                           fontSize=11, alignment=1, textColor=ROUGE)
        ))
        doc.build(elements)
        output.seek(0)
        return output

    # ===== Styles cellules =====
    cell_h = ParagraphStyle('CH', parent=styles['Normal'],
                            fontSize=7, leading=8, alignment=1,
                            textColor=colors.white, fontName='Helvetica-Bold')
    cell_h_m = ParagraphStyle('CHM', parent=styles['Normal'],
                              fontSize=8, leading=9.5, alignment=1,
                              textColor=colors.white, fontName='Helvetica-Bold')
    cell_h_b = ParagraphStyle('CHB', parent=styles['Normal'],
                              fontSize=6.5, leading=7.5, alignment=1,
                              textColor=colors.black, fontName='Helvetica-Bold')
    cell_g = ParagraphStyle('CG', parent=styles['Normal'],
                            fontSize=7.5, leading=9, alignment=1,
                            textColor=BLEU_G, fontName='Helvetica-Bold')
    cell_f = ParagraphStyle('CF', parent=styles['Normal'],
                            fontSize=7.5, leading=9, alignment=1,
                            textColor=ROSE_F, fontName='Helvetica-Bold')
    cell_t = ParagraphStyle('CT', parent=styles['Normal'],
                            fontSize=7.5, leading=9, alignment=1,
                            textColor=colors.black, fontName='Helvetica-Bold')
    cell_n = ParagraphStyle('CN', parent=styles['Normal'],
                            fontSize=7.5, leading=9, alignment=1,
                            textColor=colors.black)

    # ===== Construction des tableaux par matière =====
    # On regroupe les matières en blocs de 4 (4 par ligne)
    NB_COL = 4

    def construire_table_matiere(mc, stats):
        """Construit le mini-tableau d'une matière (tranches sur 2 lignes)."""
        nom_mat = (mc.matiere.code or mc.matiere.nom)[:10]
        header = Paragraph(f"{nom_mat}", cell_h_m)

        data = [
            # Ligne 0 : Titre matière (fusionné sur 3 colonnes)
            [header, '', ''],
            # Ligne 1 : Tranches 1 et 2
            [Paragraph('', cell_h_b),
             Paragraph("[0;6[", cell_h_b),
             Paragraph("[6;10[", cell_h_b)],
            # Ligne 2-4 : G/F/T pour les tranches 1 et 2
            [Paragraph("G", cell_g),
             Paragraph(str(stats['tranches']['G'][0]), cell_g),
             Paragraph(str(stats['tranches']['G'][1]), cell_g)],
            [Paragraph("F", cell_f),
             Paragraph(str(stats['tranches']['F'][0]), cell_f),
             Paragraph(str(stats['tranches']['F'][1]), cell_f)],
            [Paragraph("T", cell_t),
             Paragraph(str(stats['tranches']['T'][0]), cell_t),
             Paragraph(str(stats['tranches']['T'][1]), cell_t)],
            # Ligne 5 : Tranches 3 et 4
            [Paragraph('', cell_h_b),
             Paragraph("[10;15[", cell_h_b),
             Paragraph("[15;20]", cell_h_b)],
            # Ligne 6-8 : G/F/T pour les tranches 3 et 4
            [Paragraph("G", cell_g),
             Paragraph(str(stats['tranches']['G'][2]), cell_g),
             Paragraph(str(stats['tranches']['G'][3]), cell_g)],
            [Paragraph("F", cell_f),
             Paragraph(str(stats['tranches']['F'][2]), cell_f),
             Paragraph(str(stats['tranches']['F'][3]), cell_f)],
            [Paragraph("T", cell_t),
             Paragraph(str(stats['tranches']['T'][2]), cell_t),
             Paragraph(str(stats['tranches']['T'][3]), cell_t)],
        ]

        t = Table(data, colWidths=[12 * mm, 22 * mm, 22 * mm])
        t.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), BLEU_MARINE),
            ('BACKGROUND', (0, 1), (-1, 1), BLEU_CLAIR),
            ('BACKGROUND', (0, 2), (-1, 2), colors.white),
            ('BACKGROUND', (0, 3), (-1, 3), colors.white),
            ('BACKGROUND', (0, 4), (-1, 4), GRIS_CLAIR),
            ('BACKGROUND', (0, 5), (-1, 5), BLEU_CLAIR),
            ('BACKGROUND', (0, 6), (-1, 6), colors.white),
            ('BACKGROUND', (0, 7), (-1, 7), colors.white),
            ('BACKGROUND', (0, 8), (-1, 8), GRIS_CLAIR),
            ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ]))
        return t


    # Calculer les stats de toutes les matières
    stats_par_matiere = {}
    for mc in matieres_classe:
        stats_par_matiere[mc.id] = _calculer_stats_matiere(classe, trimestre, mc)

    # Construire les lignes de 4 blocs (matière)
    lignes_blocs = []
    for i in range(0, len(matieres_classe), NB_COL):
        chunk = matieres_classe[i:i + NB_COL]
        ligne = []
        for mc in chunk:
            ligne.append(construire_table_matiere(mc, stats_par_matiere[mc.id]))
        # Compléter la ligne si < 4
        while len(ligne) < NB_COL:
            ligne.append('')
        lignes_blocs.append(ligne)

    # Créer la table englobante
    grille = Table(lignes_blocs, colWidths=[70 * mm] * NB_COL)
    grille.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(grille)
    elements.append(Spacer(1, 2 * mm))

    # ===== Statistiques de la composition =====
    stats_g = _calculer_stats_globales(classe, trimestre)

    section_titre = Table(
        [[Paragraph("STATISTIQUES DE LA COMPOSITION", section_style_visible)]],
        colWidths=[285 * mm],
        rowHeights=[6 * mm],
    )
    section_titre.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(section_titre)
    elements.append(Spacer(1, 1.5 * mm))

    # Tableau stats globales
    stat_header = [
        Paragraph("", cell_h),
        Paragraph("INSCRITS", cell_h),
        Paragraph("", cell_h),
        Paragraph("", cell_h),
        Paragraph("PRÉSENTS", cell_h),
        Paragraph("", cell_h),
        Paragraph("", cell_h),
        Paragraph("MOYENNE ≥ 10", cell_h),
        Paragraph("", cell_h),
        Paragraph("", cell_h),
    ]
    stat_sous_header = [
        Paragraph("", cell_h),
        Paragraph("G", cell_h),
        Paragraph("F", cell_h),
        Paragraph("T", cell_h),
        Paragraph("G", cell_h),
        Paragraph("F", cell_h),
        Paragraph("T", cell_h),
        Paragraph("G", cell_h),
        Paragraph("F", cell_h),
        Paragraph("T", cell_h),
    ]
    stat_valeurs = [
        Paragraph("Effectif", cell_t),
        Paragraph(str(stats_g['inscrits_g']), cell_g),
        Paragraph(str(stats_g['inscrits_f']), cell_f),
        Paragraph(str(stats_g['inscrits_t']), cell_t),
        Paragraph(str(stats_g['presents_g']), cell_g),
        Paragraph(str(stats_g['presents_f']), cell_f),
        Paragraph(str(stats_g['presents_t']), cell_t),
        Paragraph(str(stats_g['moy_ok_g']), cell_g),
        Paragraph(str(stats_g['moy_ok_f']), cell_f),
        Paragraph(str(stats_g['moy_ok_t']), cell_t),
    ]

    stat_table = Table(
        [stat_header, stat_sous_header, stat_valeurs],
        colWidths=[25 * mm] + [20 * mm] * 9,
    )
    stat_table.setStyle(TableStyle([
        ('SPAN', (1, 0), (3, 0)),
        ('SPAN', (4, 0), (6, 0)),
        ('SPAN', (7, 0), (9, 0)),
        ('BACKGROUND', (0, 0), (-1, 1), BLEU_MARINE),
        ('BACKGROUND', (1, 0), (3, 0), BLEU_G),
        ('BACKGROUND', (4, 0), (6, 0), VERT),
        ('BACKGROUND', (7, 0), (9, 0), ROUGE),
        ('BACKGROUND', (0, 2), (-1, 2), GRIS_CLAIR),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(stat_table)
    elements.append(Spacer(1, 2 * mm))

    # ===== Moyennes des notes (par matière) =====
    section_titre2 = Table(
        [[Paragraph("MOYENNES DES NOTES", section_style_visible)]],
        colWidths=[285 * mm],
        rowHeights=[6 * mm],
    )
    section_titre2.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(section_titre2)
    elements.append(Spacer(1, 1.5 * mm))

    moy_header = [Paragraph("MATIÈRE", cell_h)]
    for mc in matieres_classe:
        moy_header.append(Paragraph((mc.matiere.code or mc.matiere.nom)[:8], cell_h))

    moy_values = [Paragraph("Moyenne", cell_t)]
    for mc in matieres_classe:
        s = stats_par_matiere[mc.id]
        v = s['moy_t']
        style = cell_g if v is not None and v >= 10 else (cell_f if v is not None else cell_n)
        moy_values.append(Paragraph(_fmt2(v), style))

    nb_col_moy = len(matieres_classe) + 1
    largeur_dispo_mm = 283
    largeur_matiere_mm = min(30, (largeur_dispo_mm - 30) / max(1, len(matieres_classe)))
    col_widths_moy = [30 * mm] + [largeur_matiere_mm * mm] * len(matieres_classe)

    moy_table = Table(
        [moy_header, moy_values],
        colWidths=col_widths_moy,
    )
    moy_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLEU_MARINE),
        ('BACKGROUND', (0, 1), (0, 1), GRIS_CLAIR),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(moy_table)
    elements.append(Spacer(1, 1.5 * mm))

    # ===== Pied de page =====
    pied_style = ParagraphStyle(
        'Pied', parent=styles['Normal'],
        fontSize=7, leading=9, alignment=2,
        textColor=GRIS_TEXTE, fontName='Helvetica-Oblique',
    )
    pied_txt = f"Statistiques générées le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    if utilisateur:
        nom_util = utilisateur.get_full_name() or utilisateur.username
        pied_txt += f" par {nom_util}"
    # Pied de page supprimé pour gagner de la place

    doc.build(elements)
    output.seek(0)
    return output


# =====================================================
# PAGE 2 — STATISTIQUES COMPLÈTES DU TRIMESTRE
# =====================================================
def _calculer_stats_trimestre(classe, trimestre):
    """
    Calcule toutes les données nécessaires pour la Page 2 :
    - Effectifs par sexe
    - Présents / Moy ≥ 10 / Pourcentages
    - Forte / faible moyenne + détenteurs
    - Nombre de moyennes ≥ 10 par matière
    - Analyse par intervalles (7 tranches)
    - Mentions (Félicitations / Tableau d'honneur / Encouragements / Passable)
    """
    from core.models import Note, Inscription, MatiereClasse

    inscriptions = list(
        Inscription.objects.filter(classe=classe, actif=True)
        .select_related('eleve')
    )
    eleves = [i.eleve for i in inscriptions]
    total_g = sum(1 for e in eleves if e.sexe == 'M')
    total_f = sum(1 for e in eleves if e.sexe == 'F')

    matieres_classe = list(
        MatiereClasse.objects.filter(classe=classe)
        .select_related('matiere')
        .order_by('matiere__ordre', 'matiere__nom')
    )
    matieres_ids = [mc.matiere_id for mc in matieres_classe]
    coefs_map = {mc.matiere_id: mc.coefficient for mc in matieres_classe}

    # Récupérer toutes les notes
    notes_qs = Note.objects.filter(
        eleve__in=eleves,
        matiere_id__in=matieres_ids,
        trimestre=trimestre,
    )
    notes_par_eleve = {}
    for n in notes_qs:
        notes_par_eleve.setdefault(n.eleve_id, []).append(n)

    # ===== Calcul par élève =====
    eleves_data = []
    presents_g = presents_f = 0
    moy_ok_g = moy_ok_f = 0
    forte_moy = None
    faible_moy = None
    forte_detenteur = "—"
    faible_detenteur = "—"

    # Compteurs mentions
    mentions = {
        'felicitations': {'G': 0, 'F': 0, 'T': 0},   # ≥ 16
        'honneur':      {'G': 0, 'F': 0, 'T': 0},   # ≥ 14
        'encouragement':{'G': 0, 'F': 0, 'T': 0},   # ≥ 12
        'passable':     {'G': 0, 'F': 0, 'T': 0},   # ≥ 10
    }

    # Compteurs nombres de moyennes ≥ 10 par matière
    moy_ok_par_matiere = {}
    for mc in matieres_classe:
        moy_ok_par_matiere[mc.matiere_id] = {'G': 0, 'F': 0, 'T': 0}

    # 7 tranches pour analyse par intervalles
    tranches_7 = [0, 0, 0, 0, 0, 0, 0]
    # [0;7[ [7;10[ [10;12[ [12;14[ [14;16[ [16;18[ [18;20]

    for eleve in eleves:
        notes_eleve = notes_par_eleve.get(eleve.id, [])

        # Élève présent ?
        a_notes = any(n.moyenne_finale is not None for n in notes_eleve)
        if a_notes:
            if eleve.sexe == 'M':   presents_g += 1
            elif eleve.sexe == 'F': presents_f += 1

        # Moyenne élève
        total_pts = Decimal('0')
        coef_sum = Decimal('0')
        for n in notes_eleve:
            if n.moyenne_finale is None:
                continue
            c = Decimal(str(coefs_map.get(n.matiere_id, 1)))
            total_pts += Decimal(str(n.moyenne_finale)) * c
            coef_sum += c

        if coef_sum == 0:
            continue

        moy_eleve = float(total_pts / coef_sum)

        # Moy ≥ 10 ?
        if moy_eleve >= 10:
            if eleve.sexe == 'M':   moy_ok_g += 1
            elif eleve.sexe == 'F': moy_ok_f += 1

        # Forte / faible moyenne
        if forte_moy is None or moy_eleve > forte_moy:
            forte_moy = moy_eleve
            forte_detenteur = eleve.nom_complet
        if faible_moy is None or moy_eleve < faible_moy:
            faible_moy = moy_eleve
            faible_detenteur = eleve.nom_complet

        # Mentions
        sexe_key = 'G' if eleve.sexe == 'M' else ('F' if eleve.sexe == 'F' else None)
        if moy_eleve >= 16:
            mentions['felicitations'][sexe_key] = mentions['felicitations'].get(sexe_key, 0) + 1
            mentions['felicitations']['T'] += 1
        if moy_eleve >= 14:
            mentions['honneur'][sexe_key] = mentions['honneur'].get(sexe_key, 0) + 1
            mentions['honneur']['T'] += 1
        if moy_eleve >= 12:
            mentions['encouragement'][sexe_key] = mentions['encouragement'].get(sexe_key, 0) + 1
            mentions['encouragement']['T'] += 1
        if moy_eleve >= 10:
            mentions['passable'][sexe_key] = mentions['passable'].get(sexe_key, 0) + 1
            mentions['passable']['T'] += 1

        # Tranches 7 (analyse par intervalles)
        if moy_eleve < 7:      tranches_7[0] += 1
        elif moy_eleve < 10:   tranches_7[1] += 1
        elif moy_eleve < 12:   tranches_7[2] += 1
        elif moy_eleve < 14:   tranches_7[3] += 1
        elif moy_eleve < 16:   tranches_7[4] += 1
        elif moy_eleve < 18:   tranches_7[5] += 1
        else:                  tranches_7[6] += 1

        # Nombre de moyennes ≥ 10 par matière pour cet élève
        for n in notes_eleve:
            if n.moyenne_finale is not None and float(n.moyenne_finale) >= 10:
                mid = n.matiere_id
                if mid in moy_ok_par_matiere:
                    k = 'G' if eleve.sexe == 'M' else ('F' if eleve.sexe == 'F' else None)
                    if k:
                        moy_ok_par_matiere[mid][k] += 1
                    moy_ok_par_matiere[mid]['T'] += 1

    # Moyenne de la classe
    if eleves_data:
        moy_classe = None
    else:
        # Récupérer toutes les moyennes des élèves
        toutes_moy = []
        for eleve in eleves:
            notes_eleve = notes_par_eleve.get(eleve.id, [])
            total_pts = Decimal('0')
            coef_sum = Decimal('0')
            for n in notes_eleve:
                if n.moyenne_finale is None:
                    continue
                c = Decimal(str(coefs_map.get(n.matiere_id, 1)))
                total_pts += Decimal(str(n.moyenne_finale)) * c
                coef_sum += c
            if coef_sum > 0:
                toutes_moy.append(float(total_pts / coef_sum))
        moy_classe = round(sum(toutes_moy) / len(toutes_moy), 2) if toutes_moy else None

    # Pourcentages de réussite
    total_t = total_g + total_f
    pct_g = round((moy_ok_g / total_g * 100), 2) if total_g > 0 else 0
    pct_f = round((moy_ok_f / total_f * 100), 2) if total_f > 0 else 0
    pct_t = round(((moy_ok_g + moy_ok_f) / total_t * 100), 2) if total_t > 0 else 0

    return {
        'inscrits': {'G': total_g, 'F': total_f, 'T': total_t},
        'presents': {'G': presents_g, 'F': presents_f, 'T': presents_g + presents_f},
        'moy_ok': {'G': moy_ok_g, 'F': moy_ok_f, 'T': moy_ok_g + moy_ok_f},
        'pourcentage': {'G': pct_g, 'F': pct_f, 'T': pct_t},
        'forte_moy': forte_moy,
        'faible_moy': faible_moy,
        'forte_detenteur': forte_detenteur,
        'faible_detenteur': faible_detenteur,
        'moy_classe': moy_classe,
        'moy_ok_par_matiere': moy_ok_par_matiere,
        'tranches_7': tranches_7,
        'mentions': mentions,
        'matieres_classe': matieres_classe,
        'total_inscrits': total_t,
    }


def exporter_stats_trimestre_pdf(classe, trimestre, config=None, utilisateur=None,
                                  annee_libelle=None):
    """Génère la Page 2 : statistiques complètes du trimestre."""
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4),
        leftMargin=5 * mm, rightMargin=5 * mm,
        topMargin=3 * mm, bottomMargin=3 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    LARGEUR_TOTALE = 285 * mm

    # ===== En-tête =====
    elements.extend(generer_entete_document(config, style='complet', orientation='paysage'))
    elements.append(Spacer(1, 1.5 * mm))

    # ===== Styles =====
    titre_style = ParagraphStyle('T2', parent=styles['Normal'],
                                  fontSize=14, leading=16, alignment=1,
                                  textColor=BLEU_MARINE, fontName='Helvetica-Bold')
    sous_titre_style = ParagraphStyle('S2', parent=styles['Normal'],
                                       fontSize=10, leading=12, alignment=1,
                                       textColor=colors.HexColor('#1F2937'), fontName='Helvetica-Bold')
    section_style = ParagraphStyle('Sec2', parent=styles['Normal'],
                                    fontSize=9, leading=11, alignment=1,
                                    textColor=colors.white, fontName='Helvetica-Bold')
    cell_h = ParagraphStyle('H2', parent=styles['Normal'],
                             fontSize=6.5, leading=8, alignment=1,
                             textColor=colors.black, fontName='Helvetica-Bold')
    cell = ParagraphStyle('C2', parent=styles['Normal'],
                           fontSize=7, leading=8.5, alignment=1,
                           textColor=colors.black)
    cell_g = ParagraphStyle('CG2', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=BLEU_G, fontName='Helvetica-Bold')
    cell_f = ParagraphStyle('CF2', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=ROSE_F, fontName='Helvetica-Bold')
    cell_t = ParagraphStyle('CT2', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=colors.black, fontName='Helvetica-Bold')
    cell_label = ParagraphStyle('CL2', parent=styles['Normal'],
                                 fontSize=7, leading=8.5, alignment=0,
                                 textColor=colors.black, fontName='Helvetica-Bold')

    # ✅ Session 19d — Couleur gris clair pour les en-têtes (Page 2)
    GRIS_ENTETE_P2 = colors.HexColor('#E5E7EB')

    # ===== Titre =====
    titre = Table(
        [[Paragraph("STATISTIQUES DES RÉSULTATS DU TRIMESTRE", titre_style)]],
        colWidths=[LARGEUR_TOTALE], rowHeights=[7 * mm],
    )
    titre.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(titre)

    sous_titre = Table(
        [[Paragraph(
            f"Classe : <b>{classe.nom}</b>  |  "
            f"{trimestre.get_numero_display()}  |  "
            f"Année scolaire : <b>{annee_libelle or '—'}</b>",
            sous_titre_style
        )]],
        colWidths=[LARGEUR_TOTALE], rowHeights=[5.5 * mm],
    )
    sous_titre.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(sous_titre)
    elements.append(Spacer(1, 2 * mm))

    # ===== Calcul =====
    data = _calculer_stats_trimestre(classe, trimestre)

    # ================================================
    # Fonction utilitaire : créer une section (bandeau + tableau)
    # ================================================
    # Style titre de section : texte bleu marine, gras, centré, souligné
    section_titre_txt_style = ParagraphStyle(
        'SecTitreTxt', parent=styles['Normal'],
        fontSize=10, leading=12, alignment=1,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )

    def creer_section(titre_txt, table):
        """Crée un bloc : titre texte bleu (sans bandeau) + tableau."""
        largeur = LARGEUR_TOTALE

        # Ligne de titre : texte centré bleu marine, sans fond
        titre_ligne = Table(
            [[Paragraph(titre_txt, section_titre_txt_style)]],
            colWidths=[largeur], rowHeights=[5.5 * mm],
        )
        titre_ligne.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            # Ligne de séparation sous le titre
            ('LINEBELOW', (0, 0), (-1, -1), 0.8, BLEU_MARINE),
        ]))

        # Bloc englobant : titre + tableau
        bloc = Table(
            [[titre_ligne], [table]],
            colWidths=[largeur],
        )
        bloc.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return bloc

    # ================================================
    # SECTION 1 : STATS GÉNÉRALES
    # ================================================
    tbl1_header1 = [
        Paragraph("INSCRITS", cell_h), Paragraph("", cell_h), Paragraph("", cell_h),
        Paragraph("PRÉSENTS", cell_h), Paragraph("", cell_h), Paragraph("", cell_h),
        Paragraph("MOYENNE ≥ 10", cell_h), Paragraph("", cell_h), Paragraph("", cell_h),
        Paragraph("POURCENTAGE", cell_h), Paragraph("", cell_h), Paragraph("", cell_h),
    ]
    tbl1_header2 = [
        Paragraph("G", cell_h), Paragraph("F", cell_h), Paragraph("T", cell_h),
        Paragraph("G", cell_h), Paragraph("F", cell_h), Paragraph("T", cell_h),
        Paragraph("G", cell_h), Paragraph("F", cell_h), Paragraph("T", cell_h),
        Paragraph("G", cell_h), Paragraph("F", cell_h), Paragraph("T", cell_h),
    ]
    tbl1_valeurs = [
        Paragraph(str(data['inscrits']['G']), cell_g),
        Paragraph(str(data['inscrits']['F']), cell_f),
        Paragraph(str(data['inscrits']['T']), cell_t),
        Paragraph(str(data['presents']['G']), cell_g),
        Paragraph(str(data['presents']['F']), cell_f),
        Paragraph(str(data['presents']['T']), cell_t),
        Paragraph(str(data['moy_ok']['G']), cell_g),
        Paragraph(str(data['moy_ok']['F']), cell_f),
        Paragraph(str(data['moy_ok']['T']), cell_t),
        Paragraph(f"{data['pourcentage']['G']}%", cell_g),
        Paragraph(f"{data['pourcentage']['F']}%", cell_f),
        Paragraph(f"{data['pourcentage']['T']}%", cell_t),
    ]

    tbl1 = Table(
        [tbl1_header1, tbl1_header2, tbl1_valeurs],
        colWidths=[LARGEUR_TOTALE / 12] * 12,
    )
    tbl1.setStyle(TableStyle([
        ('SPAN', (0, 0), (2, 0)),
        ('SPAN', (3, 0), (5, 0)),
        ('SPAN', (6, 0), (8, 0)),
        ('SPAN', (9, 0), (11, 0)),
        ('BACKGROUND', (0, 0), (-1, 1), GRIS_ENTETE_P2),
        ('BACKGROUND', (0, 0), (2, 0), GRIS_ENTETE_P2),
        ('BACKGROUND', (3, 0), (5, 0), GRIS_ENTETE_P2),
        ('BACKGROUND', (6, 0), (8, 0), GRIS_ENTETE_P2),
        ('BACKGROUND', (9, 0), (11, 0), GRIS_ENTETE_P2),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(creer_section("STATISTIQUES GÉNÉRALES DU TRIMESTRE", tbl1))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 2 : FORTE / FAIBLE / MOY CLASSE
    # ================================================
    forte_txt = f"{data['forte_moy']:.2f}" if data['forte_moy'] is not None else "—"
    faible_txt = f"{data['faible_moy']:.2f}" if data['faible_moy'] is not None else "—"
    moy_class_txt = f"{data['moy_classe']:.2f}" if data['moy_classe'] is not None else "—"

    tbl2_header = [
        Paragraph("FORTE MOYENNE", cell_h),
        Paragraph("DÉTENUE PAR", cell_h),
        Paragraph("FAIBLE MOYENNE", cell_h),
        Paragraph("DÉTENUE PAR", cell_h),
        Paragraph("MOY. TRIM. CLASSE", cell_h),
    ]
    tbl2_valeurs = [
        Paragraph(forte_txt, cell_t),
        Paragraph(data['forte_detenteur'][:30], cell_label),
        Paragraph(faible_txt, cell_t),
        Paragraph(data['faible_detenteur'][:30], cell_label),
        Paragraph(moy_class_txt, cell_t),
    ]
    tbl2 = Table([tbl2_header, tbl2_valeurs],
                 colWidths=[LARGEUR_TOTALE * 0.13, LARGEUR_TOTALE * 0.28,
                            LARGEUR_TOTALE * 0.13, LARGEUR_TOTALE * 0.28,
                            LARGEUR_TOTALE * 0.18])
    tbl2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P2),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('ALIGN', (3, 0), (3, -1), 'LEFT'),
        ('ALIGN', (4, 0), (4, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(creer_section("MOYENNES EXTRÊMES DU TRIMESTRE", tbl2))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 3 : NOMBRE DE MOYENNES ≥ 10 PAR MATIÈRE
    # ================================================
    matieres = data['matieres_classe']
    nb_mat = len(matieres)

    # Découper en 2 groupes de matières max (pour tenir en largeur)
    NB_PAR_GROUPE = 6
    groupes = [matieres[i:i + NB_PAR_GROUPE] for i in range(0, nb_mat, NB_PAR_GROUPE)]

    for idx_g, groupe in enumerate(groupes):
        # Ligne 1 : noms des matières (fusion 2 col chacun)
        header_l1 = [Paragraph("", cell_h)]
        for mc in groupe:
            header_l1.append(Paragraph((mc.matiere.code or mc.matiere.nom)[:8], cell_h))
            header_l1.append(Paragraph("", cell_h))

        header_l2 = [Paragraph("", cell_h)]
        for mc in groupe:
            header_l2.append(Paragraph("Nb", cell_h))
            header_l2.append(Paragraph("%", cell_h))

        def ligne_par_sexe(sexe):
            ligne = [Paragraph(sexe, cell_g if sexe == 'G' else (cell_f if sexe == 'F' else cell_t))]
            for mc in groupe:
                s = data['moy_ok_par_matiere'].get(mc.matiere_id, {'G': 0, 'F': 0, 'T': 0})
                total = data['inscrits'][sexe] if sexe in ('G', 'F') else data['inscrits']['T']
                nb = s.get(sexe, 0)
                pct = round((nb / total * 100), 2) if total > 0 else 0
                st = cell_g if sexe == 'G' else (cell_f if sexe == 'F' else cell_t)
                ligne.append(Paragraph(str(nb), st))
                ligne.append(Paragraph(f"{pct}%", st))
            return ligne

        # Largeur : 10mm (col sexe) + matières × (2 × largeur_mat)
        col_sexe = 8 * mm
        reste = LARGEUR_TOTALE - col_sexe
        largeur_mat = reste / (len(groupe) * 2)

        tbl3 = Table(
            [header_l1, header_l2, ligne_par_sexe('G'), ligne_par_sexe('F'), ligne_par_sexe('T')],
            colWidths=[col_sexe] + [largeur_mat] * (len(groupe) * 2),
        )
        tbl3.setStyle(TableStyle([
            *[('SPAN', (1 + i * 2, 0), (2 + i * 2, 0)) for i in range(len(groupe))],
            ('SPAN', (0, 0), (0, 1)),
            ('BACKGROUND', (0, 0), (-1, 1), GRIS_ENTETE_P2),
            ('BACKGROUND', (0, 2), (-1, 2), colors.white),
            ('BACKGROUND', (0, 3), (-1, 3), colors.white),
            ('BACKGROUND', (0, 4), (-1, 4), GRIS_CLAIR),
            ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        titre_section = "NOMBRE DE MOYENNES ≥ 10 PAR MATIÈRE"
        if idx_g > 0:
            titre_section += f" (suite)"
        elements.append(creer_section(titre_section, tbl3))
        elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 4 : ANALYSE PAR INTERVALLES
    # ================================================
    int_header = [Paragraph("Moyenne", cell_h)] + [
        Paragraph(lib, cell_h) for lib in ["[0;7[", "[7;10[", "[10;12[", "[12;14[", "[14;16[", "[16;18[", "[18;20]"]
    ]
    int_values = [Paragraph("Effectif", cell_label)] + [
        Paragraph(str(v), cell_t) for v in data['tranches_7']
    ]
    largeur_col = (LARGEUR_TOTALE - 30 * mm) / 7
    tbl4 = Table([int_header, int_values], colWidths=[30 * mm] + [largeur_col] * 7)
    tbl4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P2),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(creer_section("ANALYSE PAR INTERVALLES", tbl4))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 5 : RÉCAPITULATIF DES MENTIONS
    # ================================================
    men_header = [
        Paragraph("MENTION", cell_h),
        Paragraph("GARÇONS", cell_h),
        Paragraph("FILLES", cell_h),
        Paragraph("TOTAL", cell_h),
    ]
    men_data = [men_header]
    for label, key in [
        ("Félicitations (≥ 16)", 'felicitations'),
        ("Tableau d'honneur (≥ 14)", 'honneur'),
        ("Encouragements (≥ 12)", 'encouragement'),
        ("Passable (≥ 10)", 'passable'),
    ]:
        m = data['mentions'][key]
        men_data.append([
            Paragraph(label, cell_label),
            Paragraph(str(m.get('G', 0)), cell_g),
            Paragraph(str(m.get('F', 0)), cell_f),
            Paragraph(str(m.get('T', 0)), cell_t),
        ])

    l1 = LARGEUR_TOTALE * 0.40
    l2 = LARGEUR_TOTALE * 0.20
    tbl5 = Table(men_data, colWidths=[l1, l2, l2, l2])
    tbl5.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P2),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(creer_section("RÉCAPITULATIF DES MENTIONS", tbl5))

    doc.build(elements)
    output.seek(0)
    return output


# =====================================================
# PAGE 3 — STATISTIQUES ANNUELLES (synthèse des 3 trimestres)
# =====================================================
def _calculer_stats_annuelles(classe, annee_libelle):
    """
    Calcule toutes les données pour la Page 3 :
    - Moyennes par trimestre pour chaque élève (T1 / T2 / T3)
    - Moyenne annuelle élève + rang
    - Stats générales annuelles
    - Comparaison des 3 trimestres (moy, +forte, +faible, taux réussite)
    - Nb moy ≥ 10 par matière (sur moyenne annuelle de la matière)
    - Mentions annuelles
    """
    from core.models import Trimestre, Note, Inscription, MatiereClasse
    from decimal import Decimal

    inscriptions = list(
        Inscription.objects.filter(classe=classe, actif=True)
        .select_related('eleve')
    )
    eleves = [i.eleve for i in inscriptions]
    total_g = sum(1 for e in eleves if e.sexe == 'M')
    total_f = sum(1 for e in eleves if e.sexe == 'F')

    matieres_classe = list(
        MatiereClasse.objects.filter(classe=classe)
        .select_related('matiere')
        .order_by('matiere__ordre', 'matiere__nom')
    )
    matieres_ids = [mc.matiere_id for mc in matieres_classe]
    coefs_map = {mc.matiere_id: mc.coefficient for mc in matieres_classe}

    trimestres = list(
        Trimestre.objects.filter(
            etablissement=classe.etablissement,
            annee_scolaire=annee_libelle,
            numero__in=(1, 2, 3),
        ).order_by('numero')
    )
    trimestres_map = {t.numero: t for t in trimestres}

    # Récupérer toutes les notes de l'année
    notes_qs = Note.objects.filter(
        eleve__in=eleves,
        matiere_id__in=matieres_ids,
        trimestre__in=trimestres,
    ).select_related('trimestre')

    # notes_par_eleve[eleve_id][trimestre_numero] = {matiere_id: note}
    notes_par_eleve = {}
    for n in notes_qs:
        notes_par_eleve.setdefault(n.eleve_id, {}).setdefault(n.trimestre.numero, {})[n.matiere_id] = n

    # ===== Calcul par élève =====
    eleves_data = []

    for eleve in eleves:
        notes_trimestres = notes_par_eleve.get(eleve.id, {})
        moyennes_trimestres = {}  # {1: moy, 2: moy, 3: moy}
        # Moyenne annuelle par matière : {matiere_id: moy_annuelle}
        moy_par_matiere_tri = {}  # {matiere_id: [t1, t2, t3]}

        for t_num in (1, 2, 3):
            notes_t = notes_trimestres.get(t_num, {})
            total_pts = Decimal('0')
            coef_sum = Decimal('0')

            for mc in matieres_classe:
                n = notes_t.get(mc.matiere_id)
                if n and n.moyenne_finale is not None:
                    c = Decimal(str(coefs_map.get(mc.matiere_id, 1)))
                    total_pts += Decimal(str(n.moyenne_finale)) * c
                    coef_sum += c
                    # Stocker la note pour la moyenne annuelle de la matière
                    moy_par_matiere_tri.setdefault(mc.matiere_id, []).append(float(n.moyenne_finale))

            if coef_sum > 0:
                moyennes_trimestres[t_num] = round(float(total_pts / coef_sum), 2)
            else:
                moyennes_trimestres[t_num] = None

        # Moyenne annuelle élève = moyenne des 3 trimestres (si les 3 existent)
        vals = [moyennes_trimestres.get(n) for n in (1, 2, 3)]
        if all(v is not None for v in vals):
            moy_annuelle = round(sum(vals) / 3, 2)
        else:
            moy_annuelle = None

        # Moyenne annuelle par matière
        moy_matiere_annuelle = {}
        for mid, vals_m in moy_par_matiere_tri.items():
            moy_matiere_annuelle[mid] = round(sum(vals_m) / len(vals_m), 2) if vals_m else None

        eleves_data.append({
            'eleve': eleve,
            'moy_t1': moyennes_trimestres.get(1),
            'moy_t2': moyennes_trimestres.get(2),
            'moy_t3': moyennes_trimestres.get(3),
            'moy_annuelle': moy_annuelle,
            'moy_matiere_annuelle': moy_matiere_annuelle,
            'rang': None,
        })

    # Rangs annuels (ex-æquo gérés)
    eleves_avec_moy = [e for e in eleves_data if e['moy_annuelle'] is not None]
    eleves_avec_moy.sort(key=lambda x: -x['moy_annuelle'])
    rang_courant = 0
    rang_reel = 0
    moy_prec = None
    for e in eleves_avec_moy:
        rang_reel += 1
        if e['moy_annuelle'] != moy_prec:
            rang_courant = rang_reel
            moy_prec = e['moy_annuelle']
        e['rang'] = rang_courant

    # ===== Stats générales annuelles =====
    presents_g = presents_f = 0
    moy_ok_g = moy_ok_f = 0
    for e in eleves_data:
        if e['moy_annuelle'] is None:
            continue
        if e['eleve'].sexe == 'M':
            presents_g += 1
            if e['moy_annuelle'] >= 10: moy_ok_g += 1
        elif e['eleve'].sexe == 'F':
            presents_f += 1
            if e['moy_annuelle'] >= 10: moy_ok_f += 1

    total_t = total_g + total_f
    pct_g = round((moy_ok_g / total_g * 100), 2) if total_g > 0 else 0
    pct_f = round((moy_ok_f / total_f * 100), 2) if total_f > 0 else 0
    pct_t = round(((moy_ok_g + moy_ok_f) / total_t * 100), 2) if total_t > 0 else 0

    # ===== Comparaison des 3 trimestres =====
    compa = {}
    for t_num in (1, 2, 3):
        moyennes = [e[f'moy_t{t_num}'] for e in eleves_data if e[f'moy_t{t_num}'] is not None]
        if moyennes:
            compa[t_num] = {
                'moyenne': round(sum(moyennes) / len(moyennes), 2),
                'plus_forte': round(max(moyennes), 2),
                'plus_faible': round(min(moyennes), 2),
                'taux_reussite': round((sum(1 for m in moyennes if m >= 10) / len(moyennes)) * 100, 2),
                'nb_notes': len(moyennes),
            }
        else:
            compa[t_num] = {
                'moyenne': None, 'plus_forte': None, 'plus_faible': None,
                'taux_reussite': None, 'nb_notes': 0,
            }

    # ===== Nb moy ≥ 10 par matière (sur moyenne annuelle de la matière) =====
    moy_ok_par_matiere = {}
    for mc in matieres_classe:
        counts = {'G': 0, 'F': 0, 'T': 0}
        for e in eleves_data:
            v = e['moy_matiere_annuelle'].get(mc.matiere_id)
            if v is None:
                continue
            if v >= 10:
                sexe = e['eleve'].sexe
                if sexe == 'M': counts['G'] += 1
                elif sexe == 'F': counts['F'] += 1
                counts['T'] += 1
        moy_ok_par_matiere[mc.matiere_id] = counts

    # ===== Mentions annuelles =====
    mentions = {
        'felicitations': {'G': 0, 'F': 0, 'T': 0},
        'honneur':      {'G': 0, 'F': 0, 'T': 0},
        'encouragement':{'G': 0, 'F': 0, 'T': 0},
        'passable':     {'G': 0, 'F': 0, 'T': 0},
    }
    for e in eleves_data:
        v = e['moy_annuelle']
        if v is None:
            continue
        k = 'G' if e['eleve'].sexe == 'M' else ('F' if e['eleve'].sexe == 'F' else None)
        if v >= 16:
            mentions['felicitations'][k] = mentions['felicitations'].get(k, 0) + 1
            mentions['felicitations']['T'] += 1
        if v >= 14:
            mentions['honneur'][k] = mentions['honneur'].get(k, 0) + 1
            mentions['honneur']['T'] += 1
        if v >= 12:
            mentions['encouragement'][k] = mentions['encouragement'].get(k, 0) + 1
            mentions['encouragement']['T'] += 1
        if v >= 10:
            mentions['passable'][k] = mentions['passable'].get(k, 0) + 1
            mentions['passable']['T'] += 1

    # Moyenne annuelle de la classe
    toutes_moy = [e['moy_annuelle'] for e in eleves_data if e['moy_annuelle'] is not None]
    moy_classe_annuelle = round(sum(toutes_moy) / len(toutes_moy), 2) if toutes_moy else None

    # Trier les élèves par nom
    eleves_data.sort(key=lambda x: (x['eleve'].nom, x['eleve'].prenom))

    return {
        'eleves_data': eleves_data,
        'matieres_classe': matieres_classe,
        'trimestres': trimestres,
        'inscrits': {'G': total_g, 'F': total_f, 'T': total_t},
        'presents': {'G': presents_g, 'F': presents_f, 'T': presents_g + presents_f},
        'moy_ok': {'G': moy_ok_g, 'F': moy_ok_f, 'T': moy_ok_g + moy_ok_f},
        'pourcentage': {'G': pct_g, 'F': pct_f, 'T': pct_t},
        'comparaison': compa,
        'moy_ok_par_matiere': moy_ok_par_matiere,
        'mentions': mentions,
        'moy_classe_annuelle': moy_classe_annuelle,
    }


def exporter_stats_annuelles_pdf(classe, annee_libelle, config=None, utilisateur=None):
    """Génère la Page 3 : statistiques annuelles."""
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4),
        leftMargin=5 * mm, rightMargin=5 * mm,
        topMargin=3 * mm, bottomMargin=3 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()
    LARGEUR_TOTALE = 285 * mm

    # ===== En-tête =====
    elements.extend(generer_entete_document(config, style='complet', orientation='paysage'))
    elements.append(Spacer(1, 1.5 * mm))

    # ===== Styles =====
    titre_style = ParagraphStyle('T3', parent=styles['Normal'],
                                  fontSize=14, leading=16, alignment=1,
                                  textColor=BLEU_MARINE, fontName='Helvetica-Bold')
    sous_titre_style = ParagraphStyle('S3', parent=styles['Normal'],
                                       fontSize=10, leading=12, alignment=1,
                                       textColor=colors.HexColor('#1F2937'), fontName='Helvetica-Bold')
    section_titre_txt_style = ParagraphStyle('SecTitreTxt3', parent=styles['Normal'],
                                              fontSize=10, leading=12, alignment=1,
                                              textColor=BLEU_MARINE, fontName='Helvetica-Bold')
    cell_h = ParagraphStyle('H3', parent=styles['Normal'],
                             fontSize=6.5, leading=8, alignment=1,
                             textColor=colors.black, fontName='Helvetica-Bold')
    cell = ParagraphStyle('C3', parent=styles['Normal'],
                           fontSize=7, leading=8.5, alignment=1,
                           textColor=colors.black)
    cell_g = ParagraphStyle('CG3', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=BLEU_G, fontName='Helvetica-Bold')
    cell_f = ParagraphStyle('CF3', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=ROSE_F, fontName='Helvetica-Bold')
    cell_t = ParagraphStyle('CT3', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=colors.black, fontName='Helvetica-Bold')
    cell_label = ParagraphStyle('CL3', parent=styles['Normal'],
                                 fontSize=7, leading=8.5, alignment=0,
                                 textColor=colors.black, fontName='Helvetica-Bold')

    # ✅ Session 19e — Couleur gris clair pour les en-têtes (Page 3)
    GRIS_ENTETE_P3 = colors.HexColor('#E5E7EB')

    # ===== Titre =====
    titre = Table(
        [[Paragraph("STATISTIQUES ANNUELLES", titre_style)]],
        colWidths=[LARGEUR_TOTALE], rowHeights=[7 * mm],
    )
    titre.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(titre)

    sous_titre = Table(
        [[Paragraph(
            f"Classe : <b>{classe.nom}</b>  |  "
            f"Année scolaire : <b>{annee_libelle or '—'}</b>",
            sous_titre_style
        )]],
        colWidths=[LARGEUR_TOTALE], rowHeights=[5.5 * mm],
    )
    sous_titre.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(sous_titre)
    elements.append(Spacer(1, 2 * mm))

    # ===== Calcul =====
    data = _calculer_stats_annuelles(classe, annee_libelle)

    def creer_section(titre_txt, table):
        titre_ligne = Table(
            [[Paragraph(titre_txt, section_titre_txt_style)]],
            colWidths=[LARGEUR_TOTALE], rowHeights=[5.5 * mm],
        )
        titre_ligne.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LINEBELOW', (0, 0), (-1, -1), 0.8, BLEU_MARINE),
        ]))
        bloc = Table([[titre_ligne], [table]], colWidths=[LARGEUR_TOTALE])
        bloc.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return bloc

    # ================================================
    # SECTION 1 : STATS GÉNÉRALES ANNUELLES
    # ================================================
    tbl1_header1 = [
        Paragraph("INSCRITS", cell_h), Paragraph("", cell_h), Paragraph("", cell_h),
        Paragraph("NOTÉS (3 trim.)", cell_h), Paragraph("", cell_h), Paragraph("", cell_h),
        Paragraph("MOY ≥ 10", cell_h), Paragraph("", cell_h), Paragraph("", cell_h),
        Paragraph("POURCENTAGE", cell_h), Paragraph("", cell_h), Paragraph("", cell_h),
    ]
    tbl1_header2 = [
        Paragraph("G", cell_h), Paragraph("F", cell_h), Paragraph("T", cell_h),
        Paragraph("G", cell_h), Paragraph("F", cell_h), Paragraph("T", cell_h),
        Paragraph("G", cell_h), Paragraph("F", cell_h), Paragraph("T", cell_h),
        Paragraph("G", cell_h), Paragraph("F", cell_h), Paragraph("T", cell_h),
    ]
    tbl1_valeurs = [
        Paragraph(str(data['inscrits']['G']), cell_g),
        Paragraph(str(data['inscrits']['F']), cell_f),
        Paragraph(str(data['inscrits']['T']), cell_t),
        Paragraph(str(data['presents']['G']), cell_g),
        Paragraph(str(data['presents']['F']), cell_f),
        Paragraph(str(data['presents']['T']), cell_t),
        Paragraph(str(data['moy_ok']['G']), cell_g),
        Paragraph(str(data['moy_ok']['F']), cell_f),
        Paragraph(str(data['moy_ok']['T']), cell_t),
        Paragraph(f"{data['pourcentage']['G']}%", cell_g),
        Paragraph(f"{data['pourcentage']['F']}%", cell_f),
        Paragraph(f"{data['pourcentage']['T']}%", cell_t),
    ]
    tbl1 = Table([tbl1_header1, tbl1_header2, tbl1_valeurs],
                 colWidths=[LARGEUR_TOTALE / 12] * 12)
    tbl1.setStyle(TableStyle([
        ('SPAN', (0, 0), (2, 0)),
        ('SPAN', (3, 0), (5, 0)),
        ('SPAN', (6, 0), (8, 0)),
        ('SPAN', (9, 0), (11, 0)),
        ('BACKGROUND', (0, 0), (-1, 1), GRIS_ENTETE_P3),
        ('BACKGROUND', (0, 0), (2, 0), GRIS_ENTETE_P3),
        ('BACKGROUND', (3, 0), (5, 0), GRIS_ENTETE_P3),
        ('BACKGROUND', (6, 0), (8, 0), GRIS_ENTETE_P3),
        ('BACKGROUND', (9, 0), (11, 0), GRIS_ENTETE_P3),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(creer_section("STATISTIQUES GÉNÉRALES ANNUELLES", tbl1))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 2 : COMPARAISON DES 3 TRIMESTRES
    # ================================================
    compa = data['comparaison']
    tbl2_header = [
        Paragraph("", cell_h),
        Paragraph("MOYENNE", cell_h),
        Paragraph("PLUS FORTE", cell_h),
        Paragraph("PLUS FAIBLE", cell_h),
        Paragraph("TAUX RÉUSSITE ≥ 10", cell_h),
        Paragraph("NB ÉLÈVES NOTÉS", cell_h),
    ]
    tbl2_rows = [tbl2_header]
    for t_num in (1, 2, 3):
        c = compa[t_num]
        tbl2_rows.append([
            Paragraph(f"Trimestre {t_num}", cell_label),
            Paragraph(f"{c['moyenne']:.2f}" if c['moyenne'] is not None else "—", cell_t),
            Paragraph(f"{c['plus_forte']:.2f}" if c['plus_forte'] is not None else "—", cell_t),
            Paragraph(f"{c['plus_faible']:.2f}" if c['plus_faible'] is not None else "—", cell_t),
            Paragraph(f"{c['taux_reussite']}%" if c['taux_reussite'] is not None else "—", cell_t),
            Paragraph(str(c['nb_notes']), cell_t),
        ])

    col_w = LARGEUR_TOTALE / 6
    tbl2 = Table(tbl2_rows, colWidths=[col_w] * 6)
    tbl2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P3),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
    ]))
    elements.append(creer_section("COMPARAISON DES 3 TRIMESTRES", tbl2))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 3 : TABLEAU DES MOYENNES PAR ÉLÈVE
    # ================================================
    # Colonnes : N° | Matricule | Nom | T1 | T2 | T3 | Moy. Annuelle | Rang
    tbl3_header = [
        Paragraph("N°", cell_h),
        Paragraph("Matricule", cell_h),
        Paragraph("Nom et Prénom(s)", cell_h),
        Paragraph("T1", cell_h),
        Paragraph("T2", cell_h),
        Paragraph("T3", cell_h),
        Paragraph("Moy. Annuelle", cell_h),
        Paragraph("Rang", cell_h),
    ]
    tbl3_rows = [tbl3_header]
    for idx, e in enumerate(data['eleves_data'], start=1):
        def _fmt_val(v):
            return f"{v:.2f}" if v is not None else "—"
        def _cell_color(v, base_style):
            if v is None:
                return Paragraph("—", cell)
            return Paragraph(f"{v:.2f}", cell_g if v >= 10 else cell_f)

        tbl3_rows.append([
            Paragraph(str(idx), cell),
            Paragraph(e['eleve'].matricule or "—", cell),
            Paragraph(f"{e['eleve'].nom.upper()} {e['eleve'].prenom}", cell_label),
            _cell_color(e['moy_t1'], cell),
            _cell_color(e['moy_t2'], cell),
            _cell_color(e['moy_t3'], cell),
            _cell_color(e['moy_annuelle'], cell),
            Paragraph(str(e['rang']) if e['rang'] else "—", cell_t),
        ])

    col_widths_t3 = [
        8 * mm,      # N°
        22 * mm,     # Matricule
        78 * mm,     # Nom
        25 * mm,     # T1
        25 * mm,     # T2
        25 * mm,     # T3
        30 * mm,     # Moy annuelle
        15 * mm,     # Rang
    ]
    # On ajuste : total doit être ≤ LARGEUR_TOTALE = 285 mm
    # 8+22+78+25+25+25+30+15 = 228 mm → OK

    tbl3 = Table(tbl3_rows, colWidths=col_widths_t3, repeatRows=1)
    tbl3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P3),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'LEFT'),
        ('ALIGN', (3, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
    ]))
    elements.append(creer_section("MOYENNES PAR ÉLÈVE (3 TRIMESTRES + ANNUELLE)", tbl3))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 4 : NB MOY ≥ 10 PAR MATIÈRE (annuel)
    # ================================================
    matieres = data['matieres_classe']
    NB_PAR_GROUPE = 6
    groupes = [matieres[i:i + NB_PAR_GROUPE] for i in range(0, len(matieres), NB_PAR_GROUPE)]

    for idx_g, groupe in enumerate(groupes):
        header_l1 = [Paragraph("", cell_h)]
        for mc in groupe:
            header_l1.append(Paragraph((mc.matiere.code or mc.matiere.nom)[:8], cell_h))
            header_l1.append(Paragraph("", cell_h))

        header_l2 = [Paragraph("", cell_h)]
        for mc in groupe:
            header_l2.append(Paragraph("Nb", cell_h))
            header_l2.append(Paragraph("%", cell_h))

        def ligne_par_sexe(sexe):
            ligne = [Paragraph(sexe, cell_g if sexe == 'G' else (cell_f if sexe == 'F' else cell_t))]
            for mc in groupe:
                s = data['moy_ok_par_matiere'].get(mc.matiere_id, {'G': 0, 'F': 0, 'T': 0})
                total = data['inscrits'][sexe] if sexe in ('G', 'F') else data['inscrits']['T']
                nb = s.get(sexe, 0)
                pct = round((nb / total * 100), 2) if total > 0 else 0
                st = cell_g if sexe == 'G' else (cell_f if sexe == 'F' else cell_t)
                ligne.append(Paragraph(str(nb), st))
                ligne.append(Paragraph(f"{pct}%", st))
            return ligne

        col_sexe = 8 * mm
        reste = LARGEUR_TOTALE - col_sexe
        largeur_mat = reste / (len(groupe) * 2)

        tbl4 = Table(
            [header_l1, header_l2, ligne_par_sexe('G'), ligne_par_sexe('F'), ligne_par_sexe('T')],
            colWidths=[col_sexe] + [largeur_mat] * (len(groupe) * 2),
        )
        tbl4.setStyle(TableStyle([
            *[('SPAN', (1 + i * 2, 0), (2 + i * 2, 0)) for i in range(len(groupe))],
            ('SPAN', (0, 0), (0, 1)),
            ('BACKGROUND', (0, 0), (-1, 1), GRIS_ENTETE_P3),
            ('BACKGROUND', (0, 2), (-1, 2), colors.white),
            ('BACKGROUND', (0, 3), (-1, 3), colors.white),
            ('BACKGROUND', (0, 4), (-1, 4), GRIS_CLAIR),
            ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        titre_section = "NOMBRE DE MOYENNES ≥ 10 PAR MATIÈRE (ANNÉE)"
        if idx_g > 0:
            titre_section += " (suite)"
        elements.append(creer_section(titre_section, tbl4))
        elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 5 : RÉCAPITULATIF DES MENTIONS ANNUELLES
    # ================================================
    men_header = [
        Paragraph("MENTION", cell_h),
        Paragraph("GARÇONS", cell_h),
        Paragraph("FILLES", cell_h),
        Paragraph("TOTAL", cell_h),
    ]
    men_data = [men_header]
    for label, key in [
        ("Félicitations (≥ 16)", 'felicitations'),
        ("Tableau d'honneur (≥ 14)", 'honneur'),
        ("Encouragements (≥ 12)", 'encouragement'),
        ("Passable (≥ 10)", 'passable'),
    ]:
        m = data['mentions'][key]
        men_data.append([
            Paragraph(label, cell_label),
            Paragraph(str(m.get('G', 0)), cell_g),
            Paragraph(str(m.get('F', 0)), cell_f),
            Paragraph(str(m.get('T', 0)), cell_t),
        ])
    l1 = LARGEUR_TOTALE * 0.40
    l2 = LARGEUR_TOTALE * 0.20
    tbl5 = Table(men_data, colWidths=[l1, l2, l2, l2])
    tbl5.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P3),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(creer_section("RÉCAPITULATIF DES MENTIONS ANNUELLES", tbl5))

    doc.build(elements)
    output.seek(0)
    return output


# =====================================================
# PAGE 4 — STATISTIQUES ÉTABLISSEMENT (toutes les classes)
# =====================================================
def _calculer_stats_etablissement(etablissement, annee):
    """
    Calcule les stats de toutes les classes de l'établissement
    pour le DERNIER trimestre disponible (avec des données).
    """
    from core.models import Classe, Trimestre, Inscription, Note, MatiereClasse
    from decimal import Decimal

    # 1. Récupérer toutes les classes de l'année en cours
    classes = list(
        Classe.objects.filter(etablissement=etablissement, annee_scolaire=annee)
        .order_by('niveau', 'nom')
    )

    # 2. Récupérer tous les trimestres de l'année
    trimestres = list(
        Trimestre.objects.filter(etablissement=etablissement, annee_scolaire=annee.libelle)
        .order_by('-numero')
    )

    # 3. Trouver le dernier trimestre avec des données
    trimestre_courant = None
    for t in trimestres:
        nb_notes = Note.objects.filter(trimestre=t, eleve__etablissement=etablissement).count()
        if nb_notes > 0:
            trimestre_courant = t
            break

    # 4. Stats par classe
    classes_data = []
    total_g = 0
    total_f = 0

    for classe in classes:
        inscriptions = list(
            Inscription.objects.filter(classe=classe, actif=True).select_related('eleve')
        )
        nb_g = sum(1 for i in inscriptions if i.eleve.sexe == 'M')
        nb_f = sum(1 for i in inscriptions if i.eleve.sexe == 'F')
        total_g += nb_g
        total_f += nb_f

        # Calcul de la moyenne de la classe (si trimestre courant)
        moy_classe = None
        plus_forte = None
        plus_faible = None
        taux_reussite = None
        nb_moy_ok = 0
        nb_notes = 0

        if trimestre_courant:
            matieres_classe = list(
                MatiereClasse.objects.filter(classe=classe).select_related('matiere')
            )
            matieres_ids = [mc.matiere_id for mc in matieres_classe]
            coefs_map = {mc.matiere_id: mc.coefficient for mc in matieres_classe}

            notes_qs = Note.objects.filter(
                eleve__in=[i.eleve for i in inscriptions],
                matiere_id__in=matieres_ids,
                trimestre=trimestre_courant,
            )

            notes_par_eleve = {}
            for n in notes_qs:
                notes_par_eleve.setdefault(n.eleve_id, []).append(n)

            moyennes = []
            for insc in inscriptions:
                eleve = insc.eleve
                notes_eleve = notes_par_eleve.get(eleve.id, [])
                total_pts = Decimal('0')
                coef_sum = Decimal('0')

                for n in notes_eleve:
                    if n.moyenne_finale is None:
                        continue
                    c = Decimal(str(coefs_map.get(n.matiere_id, 1)))
                    total_pts += Decimal(str(n.moyenne_finale)) * c
                    coef_sum += c

                if coef_sum > 0:
                    moy = float(total_pts / coef_sum)
                    moyennes.append(moy)

            if moyennes:
                moy_classe = round(sum(moyennes) / len(moyennes), 2)
                plus_forte = round(max(moyennes), 2)
                plus_faible = round(min(moyennes), 2)
                nb_moy_ok = sum(1 for m in moyennes if m >= 10)
                taux_reussite = round((nb_moy_ok / len(moyennes)) * 100, 2)
                nb_notes = len(moyennes)

        classes_data.append({
            'classe': classe,
            'niveau': classe.get_niveau_display(),
            'niveau_code': classe.niveau,
            'nb_g': nb_g,
            'nb_f': nb_f,
            'nb_t': nb_g + nb_f,
            'moyenne': moy_classe,
            'plus_forte': plus_forte,
            'plus_faible': plus_faible,
            'taux_reussite': taux_reussite,
            'nb_moy_ok': nb_moy_ok,
            'nb_notes': nb_notes,
            'rang': None,
        })

    # 5. Rang de chaque classe (par moyenne décroissante)
    classes_avec_moy = [c for c in classes_data if c['moyenne'] is not None]
    classes_avec_moy.sort(key=lambda x: -x['moyenne'])
    rang = 0
    rang_reel = 0
    moy_prec = None
    for c in classes_avec_moy:
        rang_reel += 1
        if c['moyenne'] != moy_prec:
            rang = rang_reel
            moy_prec = c['moyenne']
        c['rang'] = rang

    # 6. Regroupement par niveau
    niveaux_map = {}
    for c in classes_data:
        n = c['niveau']
        if n not in niveaux_map:
            niveaux_map[n] = {'niveau': n, 'nb_classes': 0, 'nb_g': 0, 'nb_f': 0, 'nb_t': 0, 'moyennes': []}
        niveaux_map[n]['nb_classes'] += 1
        niveaux_map[n]['nb_g'] += c['nb_g']
        niveaux_map[n]['nb_f'] += c['nb_f']
        niveaux_map[n]['nb_t'] += c['nb_t']
        if c['moyenne'] is not None:
            niveaux_map[n]['moyennes'].append(c['moyenne'])

    niveaux_data = []
    for n, v in niveaux_map.items():
        moy_niveau = round(sum(v['moyennes']) / len(v['moyennes']), 2) if v['moyennes'] else None
        niveaux_data.append({
            'niveau': v['niveau'],
            'nb_classes': v['nb_classes'],
            'nb_g': v['nb_g'],
            'nb_f': v['nb_f'],
            'nb_t': v['nb_t'],
            'moyenne': moy_niveau,
        })
    niveaux_data.sort(key=lambda x: x['niveau'])

    # 7. Calcul des mentions établissement
    mentions = {
        'felicitations': {'G': 0, 'F': 0, 'T': 0},
        'honneur':      {'G': 0, 'F': 0, 'T': 0},
        'encouragement':{'G': 0, 'F': 0, 'T': 0},
        'passable':     {'G': 0, 'F': 0, 'T': 0},
    }

    if trimestre_courant:
        for classe in classes:
            inscriptions = Inscription.objects.filter(classe=classe, actif=True).select_related('eleve')
            matieres_classe = list(MatiereClasse.objects.filter(classe=classe))
            matieres_ids = [mc.matiere_id for mc in matieres_classe]
            coefs_map = {mc.matiere_id: mc.coefficient for mc in matieres_classe}

            for insc in inscriptions:
                eleve = insc.eleve
                notes_eleve = Note.objects.filter(
                    eleve=eleve, matiere_id__in=matieres_ids, trimestre=trimestre_courant
                )
                total_pts = Decimal('0')
                coef_sum = Decimal('0')
                for n in notes_eleve:
                    if n.moyenne_finale is None:
                        continue
                    c = Decimal(str(coefs_map.get(n.matiere_id, 1)))
                    total_pts += Decimal(str(n.moyenne_finale)) * c
                    coef_sum += c
                if coef_sum == 0:
                    continue
                moy = float(total_pts / coef_sum)
                k = 'G' if eleve.sexe == 'M' else ('F' if eleve.sexe == 'F' else None)
                if moy >= 16:
                    if k: mentions['felicitations'][k] += 1
                    mentions['felicitations']['T'] += 1
                if moy >= 14:
                    if k: mentions['honneur'][k] += 1
                    mentions['honneur']['T'] += 1
                if moy >= 12:
                    if k: mentions['encouragement'][k] += 1
                    mentions['encouragement']['T'] += 1
                if moy >= 10:
                    if k: mentions['passable'][k] += 1
                    mentions['passable']['T'] += 1

    return {
        'classes_data': classes_data,
        'niveaux_data': niveaux_data,
        'mentions': mentions,
        'trimestre_courant': trimestre_courant,
        'nb_classes': len(classes_data),
        'total_g': total_g,
        'total_f': total_f,
        'total_t': total_g + total_f,
    }


def exporter_stats_etablissement_pdf(etablissement, annee, config=None, utilisateur=None):
    """Génère la Page 4 : statistiques de tout l'établissement."""
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4),
        leftMargin=5 * mm, rightMargin=5 * mm,
        topMargin=3 * mm, bottomMargin=3 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()
    LARGEUR_TOTALE = 285 * mm

    # ===== En-tête =====
    elements.extend(generer_entete_document(config, style='complet', orientation='paysage'))
    elements.append(Spacer(1, 1.5 * mm))

    # ===== Styles =====
    titre_style = ParagraphStyle('T4', parent=styles['Normal'],
                                  fontSize=14, leading=16, alignment=1,
                                  textColor=BLEU_MARINE, fontName='Helvetica-Bold')
    sous_titre_style = ParagraphStyle('S4', parent=styles['Normal'],
                                       fontSize=10, leading=12, alignment=1,
                                       textColor=colors.HexColor('#1F2937'), fontName='Helvetica-Bold')
    section_titre_txt_style = ParagraphStyle('SecTitreTxt4', parent=styles['Normal'],
                                              fontSize=10, leading=12, alignment=1,
                                              textColor=BLEU_MARINE, fontName='Helvetica-Bold')
    cell_h = ParagraphStyle('H4', parent=styles['Normal'],
                             fontSize=6.5, leading=8, alignment=1,
                             textColor=colors.black, fontName='Helvetica-Bold')
    cell = ParagraphStyle('C4', parent=styles['Normal'],
                           fontSize=7, leading=8.5, alignment=1,
                           textColor=colors.black)
    cell_g = ParagraphStyle('CG4', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=BLEU_G, fontName='Helvetica-Bold')
    cell_f = ParagraphStyle('CF4', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=ROSE_F, fontName='Helvetica-Bold')
    cell_t = ParagraphStyle('CT4', parent=styles['Normal'],
                             fontSize=7, leading=8.5, alignment=1,
                             textColor=colors.black, fontName='Helvetica-Bold')
    cell_label = ParagraphStyle('CL4', parent=styles['Normal'],
                                 fontSize=7, leading=8.5, alignment=0,
                                 textColor=colors.black, fontName='Helvetica-Bold')

    # ===== Calcul =====
    data = _calculer_stats_etablissement(etablissement, annee)

    # ✅ Session 19f — Couleur gris clair pour les en-têtes (Page 4)
    GRIS_ENTETE_P4 = colors.HexColor('#E5E7EB')

    # ===== Titre =====
    titre = Table(
        [[Paragraph("STATISTIQUES DE L'ÉTABLISSEMENT", titre_style)]],
        colWidths=[LARGEUR_TOTALE], rowHeights=[7 * mm],
    )
    titre.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(titre)

    trimestre_txt = "—"
    if data['trimestre_courant']:
        trimestre_txt = data['trimestre_courant'].get_numero_display()

    sous_titre = Table(
        [[Paragraph(
            f"<b>{etablissement.nom}</b>  |  "
            f"Année scolaire : <b>{annee.libelle}</b>  |  "
            f"Trimestre : <b>{trimestre_txt}</b>",
            sous_titre_style
        )]],
        colWidths=[LARGEUR_TOTALE], rowHeights=[5.5 * mm],
    )
    sous_titre.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(sous_titre)
    elements.append(Spacer(1, 2 * mm))

    def creer_section(titre_txt, table):
        titre_ligne = Table(
            [[Paragraph(titre_txt, section_titre_txt_style)]],
            colWidths=[LARGEUR_TOTALE], rowHeights=[5.5 * mm],
        )
        titre_ligne.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LINEBELOW', (0, 0), (-1, -1), 0.8, BLEU_MARINE),
        ]))
        bloc = Table([[titre_ligne], [table]], colWidths=[LARGEUR_TOTALE])
        bloc.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        return bloc

    # ================================================
    # SECTION 1 : SYNTHÈSE GÉNÉRALE
    # ================================================
    tbl1_header = [
        Paragraph("NOMBRE DE CLASSES", cell_h),
        Paragraph("EFFECTIF TOTAL", cell_h),
        Paragraph("GARÇONS", cell_h),
        Paragraph("FILLES", cell_h),
        Paragraph("TAUX DE RÉUSSITE MOYEN", cell_h),
    ]
    # Taux de réussite moyen : moyenne des taux de toutes les classes
    taux_list = [c['taux_reussite'] for c in data['classes_data'] if c['taux_reussite'] is not None]
    taux_moyen = round(sum(taux_list) / len(taux_list), 2) if taux_list else None
    taux_txt = f"{taux_moyen}%" if taux_moyen is not None else "—"

    tbl1_values = [
        Paragraph(str(data['nb_classes']), cell_t),
        Paragraph(str(data['total_t']), cell_t),
        Paragraph(str(data['total_g']), cell_g),
        Paragraph(str(data['total_f']), cell_f),
        Paragraph(taux_txt, cell_t),
    ]
    col_w1 = LARGEUR_TOTALE / 5
    tbl1 = Table([tbl1_header, tbl1_values], colWidths=[col_w1] * 5)
    tbl1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P4),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(creer_section("SYNTHÈSE GÉNÉRALE DE L'ÉTABLISSEMENT", tbl1))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 2 : DÉTAIL PAR CLASSE
    # ================================================
    tbl2_header = [
        Paragraph("Rang", cell_h),
        Paragraph("Classe", cell_h),
        Paragraph("Niveau", cell_h),
        Paragraph("G", cell_h),
        Paragraph("F", cell_h),
        Paragraph("T", cell_h),
        Paragraph("Moyenne", cell_h),
        Paragraph("Plus forte", cell_h),
        Paragraph("Plus faible", cell_h),
        Paragraph("≥ 10 (Nb)", cell_h),
        Paragraph("Taux réussite", cell_h),
    ]

    tbl2_rows = [tbl2_header]
    for c in sorted(data['classes_data'], key=lambda x: (x['niveau_code'] or '', x['classe'].nom)):
        def _fmt_v(v):
            return f"{v:.2f}" if v is not None else "—"
        tbl2_rows.append([
            Paragraph(str(c['rang']) if c['rang'] else "—", cell_t),
            Paragraph(c['classe'].nom, cell_label),
            Paragraph(c['niveau'], cell),
            Paragraph(str(c['nb_g']), cell_g),
            Paragraph(str(c['nb_f']), cell_f),
            Paragraph(str(c['nb_t']), cell_t),
            Paragraph(_fmt_v(c['moyenne']), cell_t),
            Paragraph(_fmt_v(c['plus_forte']), cell_t),
            Paragraph(_fmt_v(c['plus_faible']), cell_t),
            Paragraph(str(c['nb_moy_ok']), cell_t),
            Paragraph(f"{c['taux_reussite']}%" if c['taux_reussite'] is not None else "—", cell_t),
        ])

    col_widths_t2 = [15 * mm, 40 * mm, 30 * mm, 15 * mm, 15 * mm, 15 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm, 25 * mm]
    # Somme = 260 mm
    tbl2 = Table(tbl2_rows, colWidths=col_widths_t2, repeatRows=1)
    tbl2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P4),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
        ('ALIGN', (2, 1), (2, -1), 'LEFT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
    ]))
    elements.append(creer_section("DÉTAIL PAR CLASSE", tbl2))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 3 : RÉPARTITION PAR NIVEAU
    # ================================================
    tbl3_header = [
        Paragraph("Niveau", cell_h),
        Paragraph("Nb classes", cell_h),
        Paragraph("G", cell_h),
        Paragraph("F", cell_h),
        Paragraph("T", cell_h),
        Paragraph("Moyenne du niveau", cell_h),
    ]
    tbl3_rows = [tbl3_header]
    for n in data['niveaux_data']:
        tbl3_rows.append([
            Paragraph(n['niveau'], cell_label),
            Paragraph(str(n['nb_classes']), cell_t),
            Paragraph(str(n['nb_g']), cell_g),
            Paragraph(str(n['nb_f']), cell_f),
            Paragraph(str(n['nb_t']), cell_t),
            Paragraph(f"{n['moyenne']:.2f}" if n['moyenne'] is not None else "—", cell_t),
        ])
    col_w3 = LARGEUR_TOTALE / 6
    tbl3 = Table(tbl3_rows, colWidths=[col_w3] * 6)
    tbl3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P4),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRIS_CLAIR]),
    ]))
    elements.append(creer_section("RÉPARTITION PAR NIVEAU", tbl3))
    elements.append(Spacer(1, 1.5 * mm))

    # ================================================
    # SECTION 4 : RÉCAPITULATIF DES MENTIONS ÉTABLISSEMENT
    # ================================================
    men_header = [
        Paragraph("MENTION", cell_h),
        Paragraph("GARÇONS", cell_h),
        Paragraph("FILLES", cell_h),
        Paragraph("TOTAL", cell_h),
    ]
    men_data = [men_header]
    for label, key in [
        ("Félicitations (≥ 16)", 'felicitations'),
        ("Tableau d'honneur (≥ 14)", 'honneur'),
        ("Encouragements (≥ 12)", 'encouragement'),
        ("Passable (≥ 10)", 'passable'),
    ]:
        m = data['mentions'][key]
        men_data.append([
            Paragraph(label, cell_label),
            Paragraph(str(m.get('G', 0)), cell_g),
            Paragraph(str(m.get('F', 0)), cell_f),
            Paragraph(str(m.get('T', 0)), cell_t),
        ])
    l1 = LARGEUR_TOTALE * 0.40
    l2 = LARGEUR_TOTALE * 0.20
    tbl4 = Table(men_data, colWidths=[l1, l2, l2, l2])
    tbl4.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GRIS_ENTETE_P4),
        ('GRID', (0, 0), (-1, -1), 0.4, BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(creer_section("RÉCAPITULATIF DES MENTIONS — ÉTABLISSEMENT", tbl4))

    doc.build(elements)
    output.seek(0)
    return output
