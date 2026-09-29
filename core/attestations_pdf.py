"""
ScolaEdu_AKEK — Génération des attestations officielles (PDF A4 portrait).
Version 6 :
  - Format officiel togolais "Je soussigné..."
  - N° = matricule élève
  - Titre du chef depuis config.titre_chef
  - En-tête (Ministère/République) et titre (Attestation/Certificat) INCHANGÉS
  - Cachet en overlay INCHANGÉ
"""
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    Image as RLImage, KeepTogether,
)

from core.entete_document import generer_entete_document


# =====================================================
# COULEURS
# =====================================================
BLEU_MARINE = colors.HexColor('#1E3A8A')
BLEU_CLAIR  = colors.HexColor('#DBEAFE')
JAUNE       = colors.HexColor('#FCD34D')
GRIS_TEXTE  = colors.HexColor('#64748B')


# =====================================================
# HELPERS
# =====================================================
MOIS_FR = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
]


def _fmt_date(d):
    if not d:
        return "—"
    try:
        return d.strftime('%d/%m/%Y')
    except Exception:
        return str(d)


def _fmt_date_longue(d):
    """Retourne '19 septembre 2017'."""
    if not d:
        return "—"
    try:
        return f"{d.day} {MOIS_FR[d.month]} {d.year}"
    except Exception:
        return str(d)


TYPES_ATTESTATIONS = {
    'inscription': {
        'titre': "ATTESTATION D'INSCRIPTION",
        'icone': 'bi-file-earmark-check',
    },
    'scolarite': {
        'titre': "ATTESTATION DE SCOLARITÉ",
        'icone': 'bi-mortarboard',
    },
    'radiation': {
        'titre': "CERTIFICAT DE RADIATION",
        'icone': 'bi-box-arrow-right',
    },
}


# =====================================================
# GÉNÉRATION PDF
# =====================================================
def exporter_attestation_pdf(eleve, type_attestation, inscription, annee,
                              etablissement, config=None, utilisateur=None,
                              motif_radiation=None):
    """Génère une attestation PDF pour un élève."""
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=8 * mm, bottomMargin=20 * mm,
    )

    # ===== Overlay : pied de page + cachet (INCHANGÉ) =====
    overlay_data = {
        'nom_util': None,
        'date_gen': datetime.now().strftime('%d/%m/%Y à %H:%M'),
        'cachet_path': None,
        'cachet_size_mm': 30,
        'cachet_x_mm': 130,
        'cachet_y_mm': 55,
    }
    if utilisateur:
        overlay_data['nom_util'] = utilisateur.get_full_name() or utilisateur.username
    if config and config.cachet_ecole:
        try:
            overlay_data['cachet_path'] = config.cachet_ecole.path
        except Exception:
            pass

    def dessiner_overlay(canvas_obj, doc_obj):
        canvas_obj.saveState()

        # Pied de page
        canvas_obj.setFont('Helvetica-Oblique', 7)
        canvas_obj.setFillColor(GRIS_TEXTE)
        texte = f"Attestation générée le {overlay_data['date_gen']}"
        if overlay_data['nom_util']:
            texte += f" par {overlay_data['nom_util']}"
        canvas_obj.drawCentredString(A4[0] / 2, 8 * mm, texte)

        # Cachet en overlay
        if overlay_data['cachet_path']:
            try:
                img = ImageReader(overlay_data['cachet_path'])
                taille = overlay_data['cachet_size_mm'] * mm
                x = overlay_data['cachet_x_mm'] * mm
                y = overlay_data['cachet_y_mm'] * mm
                canvas_obj.drawImage(
                    img, x, y,
                    width=taille, height=taille,
                    preserveAspectRatio=True, mask='auto',
                )
            except Exception:
                pass

        canvas_obj.restoreState()

    doc.onFirstPage = dessiner_overlay
    doc.onLaterPages = dessiner_overlay

    elements = []
    styles = getSampleStyleSheet()

    # ===== En-tête officiel (INCHANGÉ) =====
    elements.extend(generer_entete_document(config, style='complet', orientation='portrait'))
    elements.append(Spacer(1, 12 * mm))

    # ===== Styles =====
    # ⚠️ Titre INCHANGÉ
    titre_style = ParagraphStyle(
        'Titre', parent=styles['Normal'],
        fontSize=22, leading=26, alignment=1,
        textColor=BLEU_MARINE, fontName='Times-BoldItalic',
        spaceAfter=4,
    )
    num_style = ParagraphStyle(
        'Num', parent=styles['Normal'],
        fontSize=12, leading=15, alignment=0,
        textColor=colors.black, fontName='Helvetica-Bold',
        spaceBefore=4,
        spaceAfter=8,
    )
    soussigne_style = ParagraphStyle(
        'Soussigne', parent=styles['Normal'],
        fontSize=12.5, leading=22, alignment=4,
        textColor=colors.black,
        spaceBefore=6,
        spaceAfter=10,
    )
    info_style = ParagraphStyle(
        'Info', parent=styles['Normal'],
        fontSize=12.5, leading=20, alignment=0,
        textColor=colors.black,
        spaceBefore=2,
        spaceAfter=2,
    )
    conclusion_style = ParagraphStyle(
        'Conclusion', parent=styles['Normal'],
        fontSize=12.5, leading=22, alignment=4,
        textColor=colors.black,
        spaceBefore=10,
        spaceAfter=8,
    )
    fait_a_style = ParagraphStyle(
        'FaitA', parent=styles['Normal'],
        fontSize=12, leading=16, alignment=2,
        textColor=colors.black,
        spaceBefore=10,
        spaceAfter=6,
    )
    sign_titre_style = ParagraphStyle(
        'SignTitre', parent=styles['Normal'],
        fontSize=12, leading=15, alignment=2,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )
    sign_nom_style = ParagraphStyle(
        'SignNom', parent=styles['Normal'],
        fontSize=12.5, leading=15, alignment=2,
        textColor=colors.black, fontName='Helvetica-Bold',
    )
    sign_titre_chef_style = ParagraphStyle(
        'SignTitreChef', parent=styles['Normal'],
        fontSize=10.5, leading=13, alignment=2,
        textColor=GRIS_TEXTE, fontName='Helvetica-Oblique',
    )

    # ===== Titre principal (INCHANGÉ) =====
    type_info = TYPES_ATTESTATIONS.get(type_attestation, {})
    titre_txt = type_info.get('titre', "ATTESTATION")

    titre_bloc = Table(
        [[Paragraph(titre_txt, titre_style)]],
        colWidths=[170 * mm],
        rowHeights=[16 * mm],
    )
    titre_bloc.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLEU_CLAIR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('BOX', (0, 0), (-1, -1), 1, BLEU_MARINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(titre_bloc)
    elements.append(Spacer(1, 6 * mm))

    # ===== Données =====
    nom_etab = (etablissement.nom or "").upper()
    ville = "—"
    if config:
        ville = (config.ville_document or "").strip() or (config.commune or "").strip() or etablissement.ville or "—"

    nom_complet = f"{(eleve.nom or '').upper()} {eleve.prenom or ''}"
    date_naiss_longue = _fmt_date_longue(eleve.date_naissance)
    lieu_naiss = eleve.lieu_naissance or "—"
    sexe = eleve.get_sexe_display() if eleve.sexe else "—"
    matricule = eleve.matricule or "—"
    classe_nom = inscription.classe.nom if inscription and inscription.classe else "—"
    annee_libelle = annee.libelle if annee else "—"

    nom_chef = ""
    titre_chef = "Chef d'établissement"
    if config:
        nom_chef = config.nom_chef or ""
        if config.titre_chef:
            titre_chef = config.titre_chef

    # ===== N° attestation =====
    num_txt = f"N° : {matricule}"
    elements.append(Paragraph(num_txt, num_style))

    # ===== "Je soussigné..." =====
    soussigne_txt = (
        f"Je soussigné, <b>{nom_chef.upper() if nom_chef else '—'}</b>, "
        f"<b>{titre_chef}</b> du <b>{nom_etab}</b>, "
        f"certifie par la présente que :"
    )
    elements.append(Paragraph(soussigne_txt, soussigne_style))

    # ===== Bloc informations aligné =====
    # Style pour aligner les ":" — utilisation d'un Table invisible
    info_lignes = [
        ("Nom et prénoms", nom_complet),
        ("Date et lieu de naissance", f"{date_naiss_longue} à {lieu_naiss}"),
        ("Sexe", sexe),
        ("Matricule", matricule),
        ("Classe", classe_nom),
        ("Année scolaire", annee_libelle.replace('-', '–')),
    ]

    info_data = []
    for label, valeur in info_lignes:
        info_data.append([
            Paragraph(f"{label}", info_style),
            Paragraph(f": {valeur}", info_style),
        ])

    info_table = Table(info_data, colWidths=[70 * mm, 100 * mm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 0), (-1, -2), 0.2, colors.HexColor('#E2E8F0')),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 6 * mm))

    # ===== Conclusion selon le type =====
    if type_attestation == 'inscription':
        conclusion_txt = (
            f"est régulièrement <b>inscrit(e)</b> dans notre établissement "
            f"au titre de l'année scolaire <b>{annee_libelle}</b>.<br/><br/>"
            f"La présente attestation est délivrée à l'intéressé(e) pour servir "
            f"et valoir ce que de droit."
        )
    elif type_attestation == 'scolarite':
        conclusion_txt = (
            f"est régulièrement <b>inscrit(e)</b> et <b>fréquente</b> notre "
            f"établissement au titre de l'année scolaire <b>{annee_libelle}</b>.<br/><br/>"
            f"La présente attestation est délivrée à l'intéressé(e) pour servir "
            f"et valoir ce que de droit."
        )
    elif type_attestation == 'radiation':
        motif = motif_radiation or "transfert vers un autre établissement"
        conclusion_txt = (
            f"était régulièrement <b>inscrit(e)</b> dans notre établissement "
            f"au titre de l'année scolaire <b>{annee_libelle}</b>.<br/><br/>"
            f"L'élève est <b>radié(e)</b> des effectifs pour le motif suivant : "
            f"<b>{motif}</b>. Le présent certificat est délivré à l'intéressé(e) "
            f"pour servir et valoir ce que de droit."
        )
    else:
        conclusion_txt = "Attestation non reconnue."

    elements.append(Paragraph(conclusion_txt, conclusion_style))
    elements.append(Spacer(1, 6 * mm))

    # ===== Fait à + Signature =====
    date_sign = datetime.now()
    date_sign_txt = f"{date_sign.day} {MOIS_FR[date_sign.month]} {date_sign.year}"

    elements.append(Paragraph(
        f"Fait à <b>{ville.title() if ville != '—' else '—'}</b>, le <b>{date_sign_txt}</b>",
        fait_a_style
    ))

    # ===== Bloc signature (à droite) =====
    signature_img = None
    if config and config.signature_chef:
        try:
            signature_img = RLImage(config.signature_chef.path,
                                    width=38 * mm, height=13 * mm)
        except Exception:
            signature_img = None

    sign_elements = []
    sign_elements.append(Spacer(1, 4 * mm))
    if signature_img:
        sign_elements.append(signature_img)
    else:
        sign_elements.append(Spacer(1, 14 * mm))
    sign_elements.append(Spacer(1, 2 * mm))
    if nom_chef:
        sign_elements.append(Paragraph(nom_chef.upper(), sign_nom_style))

    sign_stack = Table([[e] for e in sign_elements], colWidths=[100 * mm])
    sign_stack.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    sign_final = Table(
        [['', sign_stack]],
        colWidths=[45 * mm, 125 * mm],
    )
    sign_final.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    elements.append(KeepTogether([sign_final]))

    doc.build(elements)
    output.seek(0)
    return output
