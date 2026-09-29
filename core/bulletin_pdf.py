"""
ScolaEdu_AKEK — Bulletin PDF (modèle officiel togolais).
Version 36 : équilibrée — lignes confortables + contenu remonté.
"""

from io import BytesIO
from datetime import datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
    Image as RLImage, KeepTogether,
)

from core.entete_document import generer_entete_document


LARGEUR = 19.5  # cm


# =====================================================
# BARÈME OFFICIEL TOGOLAIS
# =====================================================
def _appreciation(moy):
    if moy is None:
        return "—"
    m = float(moy)
    if m < 5:
        return "Très faible"
    if m < 7:
        return "Faible"
    if m < 9:
        return "Insuffisant"
    if m < 10:
        return "Passable"
    if m < 12:
        return "Assez bien"
    if m < 14:
        return "Bien"
    if m < 16:
        return "Très bien"
    return "Excellent"


def _mention(moy):
    if moy is None:
        return "—"
    m = float(moy)
    if m >= 16:
        return "Félicitations"
    if m >= 14:
        return "Tableau d'honneur"
    if m >= 12:
        return "Encouragements"
    if m >= 10:
        return "Admis(e)"
    return "Travail insuffisant"


def _nombre_en_lettres(moy):
    if moy is None:
        return "—"
    val = round(float(moy), 2)
    entier = int(val)
    decimale = int(round((val - entier) * 100))
    unites = ["Zero", "Un", "Deux", "Trois", "Quatre", "Cinq",
              "Six", "Sept", "Huit", "Neuf", "Dix",
              "Onze", "Douze", "Treize", "Quatorze", "Quinze",
              "Seize", "Dix-sept", "Dix-huit", "Dix-neuf", "Vingt"]
    if decimale == 0:
        if entier <= 20:
            return unites[entier]
        return f"{entier}"
    base = unites[entier] if entier <= 20 else f"{entier}"
    if decimale == 50:
        return f"{base} et demi"
    if decimale == 25:
        return f"{base} vingt-cinq"
    if decimale == 75:
        return f"{base} soixante-quinze"
    return f"{base} virgule {decimale:02d}"


def _fmt_note(v):
    if v is None:
        return "—"
    try:
        f = float(v)
        if f == int(f):
            return str(int(f))
        return f"{f:.2f}"
    except Exception:
        return str(v)


def _fmt2(v):
    if v is None:
        return ""
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)


def _fmt_entier(v):
    if v is None:
        return ""
    try:
        f = float(v)
        if f == int(f):
            return str(int(f))
        return f"{f:.2f}"
    except Exception:
        return str(v)


# =====================================================
# DÉCISION FIN D'ANNÉE
# =====================================================
def _decision_fin_annee(classe, moyenne_annuelle, note_passage):
    if moyenne_annuelle is None:
        return {
            'texte': "En attente des notes des 3 trimestres",
            'reussi': None,
            'badge_color': '#94A3B8',
        }

    seuil = float(note_passage) if note_passage else 10.0
    reussi = moyenne_annuelle >= seuil

    niveau = classe.niveau
    examens = {
        'cm2': 'CEPD',
        '3eme': 'BEPC',
        '1ere': 'BAC1',
        'tle': 'BAC2',
    }

    if niveau in examens:
        examen = examens[niveau]
        if reussi:
            return {
                'texte': f"Admis(e) à l'examen du {examen}",
                'reussi': True,
                'badge_color': '#16A34A',
            }
        else:
            return {
                'texte': f"Redouble la classe (non admis au {examen})",
                'reussi': False,
                'badge_color': '#DC2626',
            }
    else:
        if reussi:
            return {
                'texte': "Admis(e) en classe supérieure",
                'reussi': True,
                'badge_color': '#16A34A',
            }
        else:
            return {
                'texte': "Redouble la classe",
                'reussi': False,
                'badge_color': '#DC2626',
            }


# =====================================================
# CALCUL BULLETIN ÉLÈVE
# =====================================================
def _calculer_bulletin_eleve(eleve, classe, trimestre):
    from core.models import MatiereClasse, Note

    matieres_classe = MatiereClasse.objects.filter(classe=classe).select_related(
        'matiere', 'enseignant__user'
    ).order_by('matiere__ordre', 'matiere__nom')

    notes_eleve = Note.objects.filter(
        eleve=eleve,
        matiere__in=[mc.matiere for mc in matieres_classe],
        trimestre=trimestre,
    )
    notes_par_matiere = {n.matiere_id: n for n in notes_eleve}

    total_points = Decimal('0')
    somme_coefs = Decimal('0')
    lignes = []

    for mc in matieres_classe:
        note = notes_par_matiere.get(mc.matiere_id)
        moyf = note.moyenne_finale if note else None
        coef = Decimal(str(mc.coefficient))

        notes_def = None
        if moyf is not None:
            notes_def = round(float(Decimal(str(moyf)) * coef), 2)
            total_points += Decimal(str(moyf)) * coef
            somme_coefs += coef

        ens_nom = ""
        if mc.enseignant and mc.enseignant.user:
            ens_nom = (
                mc.enseignant.user.get_full_name()
                or mc.enseignant.user.username
            )

        lignes.append({
            'matiere': mc.matiere.nom,
            'dev1': note.note_devoir1 if note else None,
            'dev2': note.note_devoir2 if note else None,
            'moy_devoirs': note.moyenne_devoirs if note else None,
            'compo': note.note_composition if note else None,
            'moyenne': moyf,
            'coefficient': mc.coefficient,
            'notes_def': notes_def,
            'appreciation': _appreciation(moyf),
            'enseignant': ens_nom,
            'matiere_id': mc.matiere_id,
        })

    moyenne_trimestre = None
    if somme_coefs > 0:
        moyenne_trimestre = round(float(total_points / somme_coefs), 2)

    return {
        'lignes': lignes,
        'total_points': float(total_points),
        'total_coefs': float(somme_coefs),
        'moyenne_trimestre': moyenne_trimestre,
        'appreciation': _appreciation(moyenne_trimestre),
        'mention': _mention(moyenne_trimestre),
    }


def _rangs_par_matiere(classe, trimestre):
    from core.models import MatiereClasse, Note, Inscription

    inscriptions = Inscription.objects.filter(classe=classe, actif=True)
    eleves_ids = [i.eleve_id for i in inscriptions]
    matieres_ids = list(MatiereClasse.objects.filter(classe=classe)
                        .values_list('matiere_id', flat=True))

    rangs = {m_id: {} for m_id in matieres_ids}

    for m_id in matieres_ids:
        notes = Note.objects.filter(
            eleve_id__in=eleves_ids,
            matiere_id=m_id,
            trimestre=trimestre,
        )
        moyennes = []
        for n in notes:
            moy = n.moyenne_finale
            if moy is not None:
                moyennes.append((n.eleve_id, float(moy)))

        moyennes.sort(key=lambda x: -x[1])
        rang = 0
        rang_reel = 0
        moy_prec = None
        for eleve_id, moy in moyennes:
            rang_reel += 1
            if moy != moy_prec:
                rang = rang_reel
                moy_prec = moy
            rangs[m_id][eleve_id] = rang

    return rangs


def _moyenne_annuelle_eleve(eleve, classe, annee_libelle):
    from core.models import Trimestre, MatiereClasse, Note

    trimestres = Trimestre.objects.filter(
        etablissement=classe.etablissement,
        annee_scolaire=annee_libelle,
        numero__in=(1, 2, 3),
    )
    matieres_classe = MatiereClasse.objects.filter(classe=classe)

    moyennes_trimestres = []
    for t in trimestres:
        tot = Decimal('0')
        coef_sum = Decimal('0')
        for mc in matieres_classe:
            note = Note.objects.filter(
                eleve=eleve, matiere=mc.matiere, trimestre=t
            ).first()
            if note and note.moyenne_finale is not None:
                c = Decimal(str(mc.coefficient))
                tot += Decimal(str(note.moyenne_finale)) * c
                coef_sum += c
        if coef_sum > 0:
            moyennes_trimestres.append(float(tot / coef_sum))

    if len(moyennes_trimestres) == 3:
        return round(sum(moyennes_trimestres) / 3, 2)
    return None


def _moyennes_autres_trimestres(eleve, classe, annee_libelle, trimestre_courant_num):
    from core.models import Trimestre, MatiereClasse, Note, Inscription

    resultats = {1: None, 2: None, 3: None}
    coefs = {1: 0, 2: 0, 3: 0}
    totaux = {1: Decimal('0'), 2: Decimal('0'), 3: Decimal('0')}

    trimestres = Trimestre.objects.filter(
        etablissement=classe.etablissement,
        annee_scolaire=annee_libelle,
    )
    matieres_classe = MatiereClasse.objects.filter(classe=classe)

    for t in trimestres:
        if t.numero not in (1, 2, 3):
            continue
        if t.numero > trimestre_courant_num:
            continue
        for mc in matieres_classe:
            note = Note.objects.filter(
                eleve=eleve, matiere=mc.matiere, trimestre=t
            ).first()
            if note and note.moyenne_finale is not None:
                coef = Decimal(str(mc.coefficient))
                totaux[t.numero] += Decimal(str(note.moyenne_finale)) * coef
                coefs[t.numero] += coef

    for n in (1, 2, 3):
        if n > trimestre_courant_num:
            continue
        if coefs[n] > 0:
            resultats[n] = round(float(totaux[n] / coefs[n]), 2)

    if trimestre_courant_num == 3 and all(resultats[n] is not None for n in (1, 2, 3)):
        annuelle = round(sum(resultats[n] for n in (1, 2, 3)) / 3, 2)
    else:
        annuelle = None

    rangs = {1: None, 2: None, 3: None}

    for t_num in (1, 2, 3):
        if t_num > trimestre_courant_num:
            continue
        if resultats[t_num] is None:
            continue
        inscriptions = Inscription.objects.filter(classe=classe, actif=True)
        eleves_ids = [i.eleve_id for i in inscriptions]
        moyennes_classe = []
        for e_id in eleves_ids:
            eleve_obj = inscriptions.filter(eleve_id=e_id).first().eleve
            tot = Decimal('0')
            coef_sum = Decimal('0')
            for mc in matieres_classe:
                note = Note.objects.filter(
                    eleve=eleve_obj, matiere=mc.matiere,
                    trimestre__numero=t_num,
                    trimestre__etablissement=classe.etablissement,
                    trimestre__annee_scolaire=annee_libelle,
                ).first()
                if note and note.moyenne_finale is not None:
                    c = Decimal(str(mc.coefficient))
                    tot += Decimal(str(note.moyenne_finale)) * c
                    coef_sum += c
            if coef_sum > 0:
                moy = round(float(tot / coef_sum), 2)
                moyennes_classe.append((e_id, moy))
        moyennes_classe.sort(key=lambda x: -x[1])
        rang_courant = 0
        rang_reel = 0
        moy_prec = None
        for e_id, moy in moyennes_classe:
            rang_reel += 1
            if moy != moy_prec:
                rang_courant = rang_reel
                moy_prec = moy
            if e_id == eleve.id:
                rangs[t_num] = rang_courant
                break

    rang_annuel = None
    if trimestre_courant_num == 3 and annuelle is not None:
        inscriptions = Inscription.objects.filter(classe=classe, actif=True)
        moyennes_annuelles_classe = []
        for insc in inscriptions:
            eleve_obj = insc.eleve
            moy_ann = _moyenne_annuelle_eleve(eleve_obj, classe, annee_libelle)
            if moy_ann is not None:
                moyennes_annuelles_classe.append((eleve_obj.id, moy_ann))

        moyennes_annuelles_classe.sort(key=lambda x: -x[1])
        rang_courant = 0
        rang_reel = 0
        moy_prec = None
        for e_id, moy in moyennes_annuelles_classe:
            rang_reel += 1
            if moy != moy_prec:
                rang_courant = rang_reel
                moy_prec = moy
            if e_id == eleve.id:
                rang_annuel = rang_courant
                break

    return resultats, annuelle, rangs, rang_annuel


def _calculer_classement(classe, trimestre, inscriptions):
    resultats = []
    for insc in inscriptions:
        eleve = insc.eleve
        b = _calculer_bulletin_eleve(eleve, classe, trimestre)
        resultats.append({
            'eleve_id': eleve.id,
            'moyenne': b['moyenne_trimestre'],
        })

    resultats.sort(key=lambda r: (r['moyenne'] is None, -(r['moyenne'] or 0)))

    classement = {}
    rang = 0
    rang_reel = 0
    moy_prec = None
    for r in resultats:
        rang_reel += 1
        if r['moyenne'] != moy_prec:
            rang = rang_reel
            moy_prec = r['moyenne']
        classement[r['eleve_id']] = {
            'moyenne': r['moyenne'],
            'rang': rang if r['moyenne'] is not None else None,
        }

    moyennes = [r['moyenne'] for r in resultats if r['moyenne'] is not None]
    stats = {
        'effectif': len(resultats),
        'moyenne_classe': round(sum(moyennes) / len(moyennes), 2) if moyennes else None,
        'plus_forte': round(max(moyennes), 2) if moyennes else None,
        'plus_faible': round(min(moyennes), 2) if moyennes else None,
        'taux_reussite': round((sum(1 for m in moyennes if m >= 10) / len(moyennes)) * 100, 1) if moyennes else None,
    }

    return classement, stats


def _generer_qr_code(data, taille_mm=13):
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return RLImage(buf, width=taille_mm*mm, height=taille_mm*mm)
    except Exception:
        return None


# =====================================================
# GÉNÉRATION PDF
# =====================================================

# =====================================================
# STATS DISCIPLINE (Session 19)
# =====================================================
def _stats_discipline(eleve, trimestre):
    """
    Calcule les statistiques disciplinaires d'un élève sur la période du trimestre.
    Retourne un dict :
      retards, absences, punitions, avertissements, blames, exclusions
    """
    from core.models import IncidentDisciplinaire, Sanction

    # Filtrage par période du trimestre
    date_debut = getattr(trimestre, 'date_debut', None)
    date_fin = getattr(trimestre, 'date_fin', None)

    incidents = IncidentDisciplinaire.objects.filter(
        eleve=eleve,
        etablissement=trimestre.etablissement,
    )
    sanctions = Sanction.objects.filter(
        eleve=eleve,
        etablissement=trimestre.etablissement,
    )

    if date_debut:
        incidents = incidents.filter(date_incident__gte=date_debut)
        sanctions = sanctions.filter(date_debut__gte=date_debut)
    if date_fin:
        incidents = incidents.filter(date_incident__lte=date_fin)
        sanctions = sanctions.filter(date_debut__lte=date_fin)

    retards = incidents.filter(type_incident='retard_repete').count()
    absences = incidents.filter(type_incident='absence_non_justifiee').count()
    punitions = sanctions.filter(type_sanction='travail_supplementaire').count()
    avertissements = sanctions.filter(
        type_sanction__in=['avertissement_oral', 'avertissement_ecrit']
    ).count()
    blames = sanctions.filter(
        type_sanction__in=['renvoi_cours', 'exclusion_cours']
    ).count()
    exclusions = sanctions.filter(
        type_sanction__in=['exclusion_temporaire', 'exclusion_definitive', 'exclusion']
    ).count()

    return {
        'retards': retards,
        'absences': absences,
        'punitions': punitions,
        'avertissements': avertissements,
        'blames': blames,
        'exclusions': exclusions,
    }


def exporter_bulletins_pdf(bulletins_data, config=None, utilisateur=None, mode_lot=False):
    output = BytesIO()

    pied_de_page_data = {'nom_util': None, 'date_gen': None}
    if utilisateur:
        pied_de_page_data['nom_util'] = utilisateur.get_full_name() or utilisateur.username
    pied_de_page_data['date_gen'] = datetime.now().strftime('%d/%m/%Y')

    def dessiner_pied_de_page(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont('Helvetica-Oblique', 6.5)
        canvas_obj.setFillColor(colors.HexColor('#000000'))
        texte_nb = (
            "NB : Ce bulletin n'est delivre qu'en un seul exemplaire, "
            "le professeur principal pourra tirer une copie certifiee."
        )
        y = 5 * mm
        canvas_obj.drawString(4 * mm, y, texte_nb)
        if pied_de_page_data['nom_util']:
            texte_gen = f"Genere le {pied_de_page_data['date_gen']} par {pied_de_page_data['nom_util']}"
            canvas_obj.setFont('Helvetica-Oblique', 5.5)
            largeur_txt = canvas_obj.stringWidth(texte_gen, 'Helvetica-Oblique', 5.5)
            canvas_obj.drawString(210 * mm - 4 * mm - largeur_txt, y, texte_gen)
        canvas_obj.restoreState()

    # ✅ Bottom margin revenu à 8 mm
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=2*mm, rightMargin=2*mm,
        topMargin=2*mm, bottomMargin=8*mm,
    )
    doc.onFirstPage = dessiner_pied_de_page
    doc.onLaterPages = dessiner_pied_de_page

    elements = []
    styles = getSampleStyleSheet()

    # ===== STYLES (tailles confortables) =====
    titre_bulletin_style = ParagraphStyle(
        'TitreBulletin', parent=styles['Normal'],
        alignment=1, fontSize=16, textColor=colors.black,
        fontName='Helvetica-Bold', leading=19,
    )
    label_style = ParagraphStyle(
        'Label', parent=styles['Normal'],
        fontSize=12, textColor=colors.black, alignment=0, leading=14,
        fontName='Helvetica-Bold',
    )
    valeur_style = ParagraphStyle(
        'Valeur', parent=styles['Normal'],
        fontSize=12, textColor=colors.black, alignment=0, leading=14,
    )
    cell_bold = ParagraphStyle(
        'CellBold', parent=styles['Normal'],
        fontSize=7, textColor=colors.black, alignment=0, leading=8.5,
        fontName='Helvetica-Bold',
    )
    cell_bold_c = ParagraphStyle(
        'CellBoldC', parent=styles['Normal'],
        fontSize=7, textColor=colors.black, alignment=1, leading=8.5,
        fontName='Helvetica-Bold',
    )
    cell_bold_cb = ParagraphStyle(
        'CellBoldCB', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#1E3A8A'),
        alignment=1, leading=8.5, fontName='Helvetica-Bold',
    )
    total_style = ParagraphStyle(
        'Total', parent=styles['Normal'],
        fontSize=12.5, textColor=colors.black, alignment=0, leading=14,
        fontName='Helvetica-Bold',
    )
    total_style_c = ParagraphStyle(
        'TotalC', parent=styles['Normal'],
        fontSize=12.5, textColor=colors.black, alignment=1, leading=14,
        fontName='Helvetica-Bold',
    )
    matiere_header_style = ParagraphStyle(
        'MatiereHeader', parent=styles['Normal'],
        fontSize=14, textColor=colors.white, alignment=1, leading=16,
        fontName='Helvetica-Bold',
    )
    bloc_titre_signature = ParagraphStyle(
        'BTSig', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#1E3A8A'),
        alignment=1, leading=12, fontName='Helvetica-Bold',
    )
    nom_directeur_style = ParagraphStyle(
        'NomDirecteur', parent=styles['Normal'],
        fontSize=11, textColor=colors.black, alignment=1, leading=13,
        fontName='Helvetica-Bold',
    )
    a_affecter_style = ParagraphStyle(
        'AAffecter', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#94A3B8'),
        alignment=1, leading=9, fontName='Helvetica-Oblique',
    )
    sous_style = ParagraphStyle(
        'Sous', parent=styles['Normal'],
        alignment=1, fontSize=7.5, textColor=colors.HexColor('#64748B'),
        spaceAfter=1,
    )
    cell_style = ParagraphStyle(
        'Cell', parent=styles['Normal'],
        fontSize=7, textColor=colors.black, alignment=0, leading=8.5,
    )
    cell_c = ParagraphStyle(
        'CellC', parent=styles['Normal'],
        fontSize=7, textColor=colors.black, alignment=1, leading=8.5,
    )
    cell_c_b = ParagraphStyle(
        'CellCB', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#1E3A8A'),
        alignment=1, leading=8.5, fontName='Helvetica-Bold',
    )
    entete_col = ParagraphStyle(
        'EH', parent=styles['Normal'],
        fontSize=7.5, textColor=colors.white, alignment=1, leading=9,
        fontName='Helvetica-Bold',
    )
    entete_2lignes = ParagraphStyle(
        'E2L', parent=styles['Normal'],
        fontSize=7.5, textColor=colors.white, alignment=1, leading=9,
        fontName='Helvetica-Bold',
    )
    bloc_titre = ParagraphStyle(
        'BT', parent=styles['Normal'],
        fontSize=6.5, textColor=colors.HexColor('#1E3A8A'),
        alignment=1, leading=7.5, fontName='Helvetica-Bold',
    )
    petit_g = ParagraphStyle(
        'PG', parent=styles['Normal'],
        fontSize=6.5, textColor=colors.black, alignment=0, leading=8,
    )
    petit_g_wrap = ParagraphStyle(
        'PGW', parent=styles['Normal'],
        fontSize=6, textColor=colors.black, alignment=0, leading=7.2,
    )
    gris = ParagraphStyle(
        'Gris', parent=styles['Normal'],
        fontSize=6.5, textColor=colors.HexColor('#94A3B8'),
        alignment=0, leading=8, fontName='Helvetica-Oblique',
    )
    rouge_bold = ParagraphStyle(
        'RB', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#DC2626'),
        alignment=1, leading=11, fontName='Helvetica-Bold',
    )
    obs_decision_style = ParagraphStyle(
        'ObsDecision', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#DC2626'),
        alignment=1, leading=13, fontName='Helvetica-Bold',
    )

    for idx, data in enumerate(bulletins_data):
        eleve = data['eleve']
        classe = data['classe']
        trimestre = data['trimestre']
        bulletin = data['bulletin']
        rang = data.get('rang')
        effectif = data.get('effectif', 0)
        stats = data.get('stats', {})
        annee_libelle = trimestre.annee_scolaire

        note_passage = None
        if config and config.note_passage is not None:
            note_passage = float(config.note_passage)
        else:
            note_passage = 10.0

        rangs_matieres = _rangs_par_matiere(classe, trimestre)

        # ✅ Session 19 — Stats discipline (pour le bulletin)
        stats_discipline = _stats_discipline(eleve, trimestre)
        moy_autres, moy_annuelle, rangs_autres, rang_annuel = _moyennes_autres_trimestres(
            eleve, classe, annee_libelle, trimestre.numero
        )

        if idx == 0 or mode_lot:
            elements.extend(generer_entete_document(
                config, style='complet', orientation='portrait'
            ))
            elements.append(Spacer(1, 1.5*mm))

        # ✅ QR code revenu à 13 mm
        qr_data = f"{eleve.matricule}|{classe.nom}|{trimestre.numero}|{trimestre.annee_scolaire}"
        qr_img = _generer_qr_code(qr_data, taille_mm=13)

        if qr_img:
            ligne_qr = Table(
                [['', qr_img]],
                colWidths=[16.5*cm, 3*cm],
                hAlign='CENTER',
            )
            ligne_qr.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(ligne_qr)
            elements.append(Spacer(1, 1*mm))

        # ✅ Photo élève : 20×25 mm (compromis)
        if eleve.photo:
            try:
                photo_cell = RLImage(eleve.photo.path, width=20*mm, height=25*mm)
            except Exception:
                photo_cell = Paragraph(
                    "<para align='center'>Photo</para>", cell_c
                )
        else:
            photo_cell = Paragraph(
                "<para align='center'>Photo</para>", cell_c
            )

        col_gauche = [
            [Paragraph("Nom :", label_style), Paragraph((eleve.nom or '').upper(), valeur_style)],
            [Paragraph("Prenom(s) :", label_style), Paragraph(eleve.prenom or '', valeur_style)],
            [Paragraph("Classe :", label_style), Paragraph(classe.nom, valeur_style)],
        ]
        col_droite = [
            [Paragraph("Sexe :", label_style), Paragraph(eleve.get_sexe_display(), valeur_style)],
            [Paragraph("Statut :", label_style), Paragraph(eleve.statut or '', valeur_style)],
            [Paragraph("Effectif :", label_style), Paragraph(str(effectif), valeur_style)],
        ]

        inner_gauche_style = TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ])
        inner_droite_style = TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ])

        tg = Table(col_gauche, colWidths=[2.9*cm, 5.6*cm])
        tg.setStyle(inner_gauche_style)
        td = Table(col_droite, colWidths=[2.9*cm, 5.6*cm])
        td.setStyle(inner_droite_style)

        corps_infos = Table(
            [[tg, photo_cell, td]],
            colWidths=[8.5*cm, 2.5*cm, 8.5*cm],
            hAlign='CENTER',
        )
        corps_infos.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('LINEAFTER', (0, 0), (0, 0), 0.5, colors.HexColor('#1E3A8A')),
            ('LINEAFTER', (1, 0), (1, 0), 0.5, colors.HexColor('#1E3A8A')),
        ]))

        ligne_titre = Table(
            [[Paragraph(
                f"BULLETIN DE NOTES DU {trimestre.get_numero_display().upper()}  /  {annee_libelle}",
                titre_bulletin_style
            )]],
            colWidths=[19.5*cm],
        )
        ligne_titre.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#D1D5DB')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))

        bloc_infos = Table(
            [[ligne_titre], [corps_infos]],
            colWidths=[19.5*cm],
            hAlign='CENTER',
        )
        bloc_infos.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#1E3A8A')),
            ('LINEBELOW', (0, 0), (0, 0), 1.5, colors.HexColor('#1E3A8A')),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        elements.append(bloc_infos)
        elements.append(Spacer(1, 1.5*mm))

        # ===== TABLEAU MATIÈRES =====
        cols = [
            ('MATIERE', 4.00),
            ('DEV1', 0.95),
            ('DEV2', 0.95),
            ('MOY_CLS', 1.35),
            ('COMPO', 1.10),
            ('MOY_TRIM', 1.20),
            ('COEF', 0.85),
            ('NOTES_DEF', 1.75),
            ('RANG', 1.00),
            ('APPREC', 1.80),
            ('PROF', 2.45),
            ('SIGN', 2.10),
        ]

        ligne1 = [
            Paragraph('<b>MATIÈRES</b>', matiere_header_style),
            Paragraph('<b>Notes de</b><br/><b>Classe</b>', entete_2lignes),
            '',
            Paragraph('<b>Moy</b><br/><b>Classe</b>', entete_2lignes),
            Paragraph('<b>Compo</b>', entete_col),
            Paragraph('<b>Moy</b><br/><b>trim</b>', entete_2lignes),
            Paragraph('<b>Coef</b>', entete_col),
            Paragraph('<b>Notes</b><br/><b>def.</b>', entete_2lignes),
            Paragraph('<b>Rang</b>', entete_col),
            Paragraph('<b>Appreciation</b>', entete_col),
            Paragraph('<b>Noms des</b><br/><b>professeurs</b>', entete_2lignes),
            Paragraph('<b>Signature</b>', entete_col),
        ]
        ligne2 = [
            '',
            Paragraph('<b>Dev 1</b>', entete_col),
            Paragraph('<b>Dev 2</b>', entete_col),
            '', '', '', '', '', '', '', '',
        ]

        notes_data = [ligne1, ligne2]

        for ligne in bulletin['lignes']:
            rang_m = rangs_matieres.get(ligne['matiere_id'], {}).get(eleve.id)

            notes_data.append([
                Paragraph(ligne['matiere'][:35], cell_bold),
                Paragraph(_fmt_entier(ligne['dev1']), cell_bold_c),
                Paragraph(_fmt_entier(ligne['dev2']), cell_bold_c),
                Paragraph(_fmt2(ligne['moy_devoirs']), cell_bold_c),
                Paragraph(_fmt_entier(ligne['compo']), cell_bold_c),
                Paragraph(_fmt2(ligne['moyenne']), cell_bold_c),
                Paragraph(str(ligne['coefficient']), cell_bold_c),
                Paragraph(_fmt2(ligne['notes_def']), cell_bold_c),
                Paragraph(str(rang_m) if rang_m else '—', cell_bold_cb),
                Paragraph(ligne['appreciation'], cell_bold_c),
                Paragraph((ligne['enseignant'] or '')[:28], cell_bold),
                Paragraph('', cell_bold_c),
            ])

        notes_data.append([
            Paragraph('<b>TOTAL</b>', total_style),
            '', '', '', '', '',
            Paragraph(f"<b>{_fmt_note(bulletin['total_coefs'])}</b>", total_style_c),
            Paragraph(f"<b>{_fmt2(bulletin['total_points'])}</b>", total_style_c),
            '', '', '', '',
        ])

        nt = Table(
            notes_data,
            colWidths=[c[1]*cm for c in cols],
            repeatRows=2,
            hAlign='CENTER',
        )
        # ✅ Padding revenu à 3.5 pour aérer les lignes
        nt.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 1), colors.HexColor('#1E3A8A')),
            ('SPAN', (1, 0), (2, 0)),
            ('SPAN', (0, 0), (0, 1)),
            ('SPAN', (3, 0), (3, 1)),
            ('SPAN', (4, 0), (4, 1)),
            ('SPAN', (5, 0), (5, 1)),
            ('SPAN', (6, 0), (6, 1)),
            ('SPAN', (7, 0), (7, 1)),
            ('SPAN', (8, 0), (8, 1)),
            ('SPAN', (9, 0), (9, 1)),
            ('SPAN', (10, 0), (10, 1)),
            ('SPAN', (11, 0), (11, 1)),
            ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, 1), 'MIDDLE'),
            ('FONTNAME', (0, 2), (-1, -2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 2), (-1, -2), 7),
            ('VALIGN', (0, 2), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#FEF3C7')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#1E3A8A')),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#1E3A8A')),
            ('LINEAFTER', (0, 0), (0, 1), 1, colors.white),
            ('LINEAFTER', (1, 0), (1, 1), 1, colors.white),
            ('LINEAFTER', (2, 0), (2, 1), 1, colors.white),
            ('LINEAFTER', (3, 0), (3, 1), 1, colors.white),
            ('LINEAFTER', (4, 0), (4, 1), 1, colors.white),
            ('LINEAFTER', (5, 0), (5, 1), 1, colors.white),
            ('LINEAFTER', (6, 0), (6, 1), 1, colors.white),
            ('LINEAFTER', (7, 0), (7, 1), 1, colors.white),
            ('LINEAFTER', (8, 0), (8, 1), 1, colors.white),
            ('LINEAFTER', (9, 0), (9, 1), 1, colors.white),
            ('LINEAFTER', (10, 0), (10, 1), 1, colors.white),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.white),
            ('TOPPADDING', (0, 0), (-1, -1), 3.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(nt)
        elements.append(Spacer(1, 1.5*mm))

        # BLOC 1
        moy_txt = _fmt2(bulletin['moyenne_trimestre'])
        moy_lettres = _nombre_en_lettres(bulletin['moyenne_trimestre'])
        num = trimestre.numero
        label_moy = f"{num}er Trimestre :" if num == 1 else f"{num}e Trimestre :"

        inner_g = Table([
            [
                Paragraph(label_moy, petit_g),
                Paragraph(f"<b><font color='#DC2626'>{moy_txt}</font></b>", petit_g),
                Paragraph("Rang :", petit_g),
                Paragraph(f"<b>{rang}<sup>e</sup>/{effectif}</b>" if rang else "—", petit_g),
            ],
            [
                Paragraph("Moy en lettres :", petit_g),
                Paragraph(f"<b><font color='#DC2626'>{moy_lettres}</font></b>", petit_g_wrap),
                Paragraph("", petit_g),
                Paragraph("", petit_g),
            ],
            [
                Paragraph("Mention :", petit_g),
                Paragraph(f"<b>{bulletin['mention']}</b>", petit_g_wrap),
                Paragraph("", petit_g),
                Paragraph("", petit_g),
            ],
        ], colWidths=[2.0*cm, 2.1*cm, 0.9*cm, 1.5*cm])
        inner_g.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))

        lignes_rapp = []
        for n in (1, 2, 3):
            if n <= num:
                v = moy_autres.get(n)
                r = rangs_autres.get(n)
                if v is None:
                    val_cell = Paragraph("<font color='#94A3B8'><i>—</i></font>", gris)
                    rang_cell = Paragraph("<font color='#94A3B8'>Rang : —</font>", gris)
                else:
                    val_cell = Paragraph(f"<b>{_fmt2(v)}</b>", petit_g)
                    rang_cell = Paragraph(f"<b>Rang : {r}<sup>e</sup></b>" if r else "Rang : —", petit_g)
                lbl = f"{n}er Trimestre :" if n == 1 else f"{n}e Trimestre :"
                lignes_rapp.append([Paragraph(lbl, petit_g), val_cell, rang_cell])
            else:
                lbl = f"{n}e Trimestre :"
                lignes_rapp.append([
                    Paragraph(lbl, gris),
                    Paragraph("<font color='#94A3B8'><i>—</i></font>", gris),
                    Paragraph("<font color='#94A3B8'>Rang : —</font>", gris),
                ])

        if num == 3 and moy_annuelle is not None:
            rang_annuel_txt = f"Rang : {rang_annuel}<sup>e</sup>" if rang_annuel else "Rang : —"
            ligne_annuelle = [
                Paragraph("Moy. Annuelle :", petit_g),
                Paragraph(f"<b>{_fmt2(moy_annuelle)}</b>", petit_g),
                Paragraph(f"<b>{rang_annuel_txt}</b>", petit_g),
            ]
        else:
            ligne_annuelle = [
                Paragraph("Moy. Annuelle :", gris),
                Paragraph("<font color='#94A3B8'><i>En attente</i></font>", gris),
                Paragraph("<font color='#94A3B8'>Rang : —</font>", gris),
            ]
        lignes_rapp.append(ligne_annuelle)

        inner_rapp = Table(lignes_rapp, colWidths=[2.4*cm, 2.0*cm, 2.1*cm])
        inner_rapp.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ]))

        tg2 = Table([
            [Paragraph('<b>MOYENNES DE L\'ELEVE</b>', bloc_titre)],
            [inner_g],
            [Paragraph('<b>RAPPEL DES MOYENNES</b>', bloc_titre)],
            [inner_rapp],
        ], colWidths=[6.5*cm])
        tg2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0, 2), (0, 2), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#1E3A8A')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        # BLOC 2
        LBL_W = 3.0
        VAL_W = 2.8

        inner_c = Table([
            [Paragraph("Moy. plus forte :", petit_g), Paragraph(f"<b>{_fmt2(stats.get('plus_forte'))}</b>", petit_g)],
            [Paragraph("Moy. plus faible :", petit_g), Paragraph(f"<b>{_fmt2(stats.get('plus_faible'))}</b>", petit_g)],
            [Paragraph("Moy. de la classe :", petit_g), Paragraph(f"<b>{_fmt2(stats.get('moyenne_classe'))}</b>", petit_g)],
        ], colWidths=[LBL_W*cm, VAL_W*cm])
        inner_c.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))

        m = bulletin['moyenne_trimestre']
        fel = "Oui" if m and m >= 16 else ""
        enc = "Oui" if m and m >= 12 else ""
        tab = "Oui" if m and m >= 14 else ""

        inner_m = Table([
            [Paragraph("Felicitation :", petit_g), Paragraph(fel, petit_g)],
            [Paragraph("Encouragement :", petit_g), Paragraph(enc, petit_g)],
            [Paragraph("Tableau d'honneur :", petit_g), Paragraph(tab, petit_g)],
        ], colWidths=[LBL_W*cm, VAL_W*cm])
        inner_m.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))

        tm = Table([
            [Paragraph('<b>MOYENNES DE LA CLASSE</b>', bloc_titre)],
            [inner_c],
            [Paragraph('<b>MERITES</b>', bloc_titre)],
            [inner_m],
        ], colWidths=[6.3*cm])
        tm.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0, 2), (0, 2), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#1E3A8A')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        # BLOC 3
        inner_d = Table([
            [Paragraph("Retard", petit_g), Paragraph(f"{stats_discipline['retards']} fois", petit_g)],
            [Paragraph("Absences", petit_g), Paragraph(f"{stats_discipline['absences']} heures", petit_g)],
            [Paragraph("Punitions", petit_g), Paragraph(f"{stats_discipline['punitions']}", petit_g)],
        ], colWidths=[3.0*cm, 3.1*cm])
        inner_d.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))

        inner_s = Table([
            [Paragraph("Avertis.", petit_g), Paragraph(f"{stats_discipline['avertissements']}" if stats_discipline['avertissements'] else "", petit_g)],
            [Paragraph("Blame", petit_g), Paragraph(f"{stats_discipline['blames']}" if stats_discipline['blames'] else "", petit_g)],
            [Paragraph("Exclusion", petit_g), Paragraph(f"{stats_discipline['exclusions']}" if stats_discipline['exclusions'] else "", petit_g)],
        ], colWidths=[3.0*cm, 3.1*cm])
        inner_s.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))

        td2 = Table([
            [Paragraph('<b>DISCIPLINES</b>', bloc_titre)],
            [inner_d],
            [Paragraph('<b>SANCTIONS</b>', bloc_titre)],
            [inner_s],
        ], colWidths=[6.5*cm])
        td2.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#E2E8F0')),
            ('BACKGROUND', (0, 2), (0, 2), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#1E3A8A')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        blocs_bas = Table(
            [[tg2, '', tm, '', td2]],
            colWidths=[6.5*cm, 0.1*cm, 6.3*cm, 0.1*cm, 6.5*cm],
            hAlign='CENTER',
        )
        blocs_bas.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(blocs_bas)
        elements.append(Spacer(1, 1.5*mm))

        # OBSERVATION + DÉCISION
        if num < 3:
            obs_texte = "Travail insuffisant"
            if bulletin['moyenne_trimestre'] is not None:
                if bulletin['moyenne_trimestre'] >= 10:
                    obs_texte = f"Travail {bulletin['appreciation']} — Continue ainsi"
                else:
                    obs_texte = "Travail insuffisant — Doit redoubler d'efforts"
            ligne_decision = f"Visa du {trimestre.get_numero_display()}"
            decision_color = '#1E3A8A'
        else:
            obs_texte = "Travail insuffisant"
            if bulletin['moyenne_trimestre'] is not None:
                if bulletin['moyenne_trimestre'] >= 10:
                    obs_texte = f"Travail {bulletin['appreciation']}"
                else:
                    obs_texte = "Travail insuffisant"

            decision = _decision_fin_annee(classe, moy_annuelle, note_passage)
            ligne_decision = decision['texte']
            decision_color = decision['badge_color']

        obs_decision_html = (
            f"<font color='#DC2626'><b>{obs_texte}</b></font>"
            f" &nbsp;—&nbsp; "
            f"<font color='{decision_color}'><b>{ligne_decision}</b></font>"
        )

        date_sign = datetime.now().strftime('%d/%m/%Y')
        ville = "—"
        if config:
            ville = (
                (config.ville_document or "").strip()
                or (config.commune or "").strip()
                or "—"
            )

        obs_data = [[
            Paragraph('<b>Observation et Decisions du Conseil</b>', bloc_titre),
            Paragraph(f"Fait a <b>{ville}</b>, le <b>{date_sign}</b>", petit_g),
        ], [
            Paragraph(obs_decision_html, obs_decision_style),
            '',
        ]]
        obs_table = Table(
            obs_data,
            colWidths=[12*cm, 7.5*cm],
            hAlign='CENTER',
        )
        obs_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#1E3A8A')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))

        # SIGNATURES
        nom_chef = config.nom_chef if config and config.nom_chef else "—"

        titulaire_obj = classe.titulaire
        if titulaire_obj and titulaire_obj.user:
            nom_titulaire = (
                titulaire_obj.user.get_full_name()
                or titulaire_obj.user.username
            )
            titulaire_cell = Paragraph(
                f"<br/><br/><br/><b>{nom_titulaire}</b>",
                nom_directeur_style
            )
        else:
            titulaire_cell = Paragraph(
                "<br/><br/><br/>"
                "<font color='#94A3B8' size=7><i>(À affecter)</i></font>",
                a_affecter_style
            )

        sig_img = None
        cachet_img = None

        if config:
            if config.signature_chef:
                try:
                    sig_img = RLImage(
                        config.signature_chef.path,
                        width=23*mm, height=8*mm,
                    )
                except Exception:
                    sig_img = None
            if config.cachet_ecole:
                try:
                    cachet_img = RLImage(
                        config.cachet_ecole.path,
                        width=17*mm, height=17*mm,
                    )
                except Exception:
                    cachet_img = None

        directeur_elements = []
        directeur_elements.append(Paragraph(nom_chef.upper(), nom_directeur_style))
        directeur_elements.append(Spacer(1, 1*mm))
        if sig_img:
            directeur_elements.append(sig_img)
        else:
            directeur_elements.append(Spacer(1, 5*mm))
            directeur_elements.append(Paragraph(
                "<font color='#94A3B8' size=7><i>(Signature)</i></font>",
                a_affecter_style
            ))
        if cachet_img:
            directeur_elements.append(cachet_img)
        else:
            directeur_elements.append(Spacer(1, 6*mm))
            directeur_elements.append(Paragraph(
                "<font color='#94A3B8' size=7><i>(Cachet)</i></font>",
                a_affecter_style
            ))

        directeur_cell = Table(
            [[e] for e in directeur_elements],
            colWidths=[9.75*cm],
            hAlign='CENTER',
        )
        directeur_cell.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        sig_data = [[
            Paragraph("<b>LE TITULAIRE</b>", bloc_titre_signature),
            Paragraph("<b>LE DIRECTEUR</b>", bloc_titre_signature),
        ], [
            titulaire_cell,
            directeur_cell,
        ]]
        # ✅ Hauteur signatures : 32 mm
        sig_table = Table(
            sig_data,
            colWidths=[9.75*cm, 9.75*cm],
            hAlign='CENTER',
            rowHeights=[8*mm, 32*mm],
        )
        sig_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#1E3A8A')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))

        elements.append(KeepTogether([
            obs_table,
            Spacer(1, 1.5*mm),
            sig_table,
        ]))

        if mode_lot and idx < len(bulletins_data) - 1:
            elements.append(PageBreak())

    doc.build(elements)
    output.seek(0)
    return output
