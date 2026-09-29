"""
ScolaEdu_AKEK — Génération des cartes scolaires.
Disposition : 10 cartes par page A4 (2 colonnes × 5 lignes).

Version finale 12 :
  - Drapeau : LONGUEUR (largeur) réduite de 0,5 mm → 10,5 mm
  - Hauteur du drapeau inchangée (5,5 mm)
  - Tout le reste FIGÉ
"""
import os
from io import BytesIO
from datetime import datetime

from django.conf import settings

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    Image as RLImage, PageBreak,
)
from reportlab.graphics.shapes import Drawing, Rect, Polygon


# =====================================================
# DIMENSIONS
# =====================================================
CARTE_L = 85.6 * mm
CARTE_H = 53.98 * mm
COLS    = 2
ROWS    = 5

MARGE_PAGE = 2 * mm
GAP_X = 8 * mm
GAP_Y = 4 * mm

BORDURE = 1.2
BORDURE_MM = BORDURE * 0.3528

BORDURE_CARTE_MM = 1.4 * mm


# =====================================================
# COULEURS
# =====================================================
BLEU_MARINE = colors.HexColor('#1E3A8A')
BLEU_CLAIR  = colors.HexColor('#DBEAFE')
JAUNE       = colors.HexColor('#FCD34D')
GRIS_TEXTE  = colors.HexColor('#64748B')
ROUGE       = colors.HexColor('#DC2626')
NOIR        = colors.HexColor('#000000')


# =====================================================
# DRAPEAU TOGO DESSINÉ
# =====================================================
def _dessiner_drapeau_togo(w_mm=10.5, h_mm=5.5):
    """Drapeau Togo — largeur 10,5 mm × hauteur 5,5 mm."""
    import math
    d = Drawing(w_mm * mm, h_mm * mm)

    bande_h = (h_mm * mm) / 5
    for i in range(5):
        couleur = colors.HexColor('#006A4E') if i % 2 == 0 else colors.HexColor('#FFCE00')
        y = (h_mm * mm) - (i + 1) * bande_h
        d.add(Rect(0, y, w_mm * mm, bande_h,
                   fillColor=couleur, strokeColor=None))

    canton_w = (w_mm * mm) * 0.4
    canton_h = (h_mm * mm)
    d.add(Rect(0, 0, canton_w, canton_h,
               fillColor=colors.HexColor('#D21034'), strokeColor=None))

    cx = canton_w / 2
    cy = canton_h / 2
    r_ext = min(canton_w, canton_h) * 0.32
    r_int = r_ext * 0.4

    pts = []
    for i in range(10):
        angle = -math.pi / 2 + i * math.pi / 5
        r = r_ext if i % 2 == 0 else r_int
        pts.extend([cx + r * math.cos(angle), cy + r * math.sin(angle)])

    d.add(Polygon(pts, fillColor=colors.white, strokeColor=None))
    return d


# =====================================================
# RESSOURCES STATIQUES
# =====================================================
def _chemin_static(*parts):
    return os.path.join(settings.BASE_DIR, 'static', 'images', *parts)


def _img_si_existe(path, w_mm, h_mm):
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return RLImage(path, width=w_mm * mm, height=h_mm * mm)
    except Exception:
        pass
    return None


def _drapeau_ou_dessin(w_mm=10.5, h_mm=5.5):
    path = _chemin_static('drapeau_togo.png')
    img = _img_si_existe(path, w_mm, h_mm)
    if img:
        return img
    return _dessiner_drapeau_togo(w_mm, h_mm)


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


def _valeur(v, defaut="—"):
    if v is None:
        return defaut
    s = str(v).strip()
    return s if s else defaut


def _tronquer(txt, max_len=30):
    if not txt:
        return ""
    s = str(txt)
    return s if len(s) <= max_len else s[:max_len - 1] + "…"


def _generer_qr_code(data, taille_mm=14):
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=0)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return RLImage(buf, width=taille_mm * mm, height=taille_mm * mm)
    except Exception:
        return None


# =====================================================
# CONSTRUCTION D'UNE CARTE
# =====================================================
def _construire_carte(eleve, classe, annee_libelle, config, etablissement):
    styles = getSampleStyleSheet()

    s_pays = ParagraphStyle(
        'CartePays', parent=styles['Normal'],
        fontSize=7.5, leading=8, alignment=1,
        textColor=colors.white, fontName='Helvetica-Bold',
    )
    s_devise_pays = ParagraphStyle(
        'CarteDevisePays', parent=styles['Normal'],
        fontSize=4.8, leading=5, alignment=1,
        textColor=colors.white, fontName='Helvetica-Oblique',
    )
    s_etab = ParagraphStyle(
        'CarteEtab', parent=styles['Normal'],
        fontSize=10, leading=11.5, alignment=1,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )
    s_titre_carte = ParagraphStyle(
        'CarteTitre', parent=styles['Normal'],
        fontSize=9.5, leading=10.5, alignment=1,
        textColor=colors.white, fontName='Helvetica-Bold',
    )
    s_annee = ParagraphStyle(
        'CarteAnnee', parent=styles['Normal'],
        fontSize=9, leading=10.5, alignment=1,
        textColor=colors.HexColor('#7C2D12'), fontName='Helvetica-Bold',
    )
    s_label = ParagraphStyle(
        'CarteLabel', parent=styles['Normal'],
        fontSize=6.8, leading=8.2,
        textColor=BLEU_MARINE, fontName='Helvetica-Bold',
    )
    s_valeur = ParagraphStyle(
        'CarteValeur', parent=styles['Normal'],
        fontSize=7.2, leading=8.4,
        textColor=colors.black, fontName='Helvetica-Bold',
    )
    s_valeur_rouge = ParagraphStyle(
        'CarteVR', parent=styles['Normal'],
        fontSize=7.8, leading=9,
        textColor=ROUGE, fontName='Helvetica-Bold',
    )
    s_pied_chef = ParagraphStyle(
        'CartePiedChef', parent=styles['Normal'],
        fontSize=5.5, leading=6.5, alignment=0,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    s_pied_titre = ParagraphStyle(
        'CartePiedTitre', parent=styles['Normal'],
        fontSize=5, leading=6, alignment=0,
        textColor=NOIR, fontName='Helvetica-Oblique',
    )
    s_pied_tel = ParagraphStyle(
        'CartePiedTel', parent=styles['Normal'],
        fontSize=5.2, leading=6.4, alignment=0,
        textColor=NOIR, fontName='Helvetica-Bold',
    )
    s_pied_fait = ParagraphStyle(
        'CartePiedFait', parent=styles['Normal'],
        fontSize=5.2, leading=6.4, alignment=2,
        textColor=NOIR, fontName='Helvetica-Oblique',
    )

    nom_etab = (etablissement.nom or "").upper()

    L_utile = CARTE_L - 2 * BORDURE_CARTE_MM + 2 * mm

    # ---- Bandeau République ----
    bandeau_pays = Table(
        [[Paragraph("RÉPUBLIQUE TOGOLAISE", s_pays)],
         [Paragraph("Travail — Liberté — Patrie", s_devise_pays)]],
        colWidths=[L_utile],
        rowHeights=[3.4 * mm, 2.4 * mm],
    )
    bandeau_pays.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # ---- Bandeau ÉTABLISSEMENT ----
    armoirie_path = None
    if etablissement.logo:
        try:
            armoirie_path = etablissement.logo.path
        except Exception:
            armoirie_path = None
    if not armoirie_path:
        armoirie_path = _chemin_static('armoiries_togo.png')

    armoirie_img = _img_si_existe(armoirie_path, 5.5, 6.5)
    # 🎯 Drapeau : LONGUEUR (largeur) réduite → 10,5 mm, hauteur inchangée 5,5 mm
    drapeau_img = _drapeau_ou_dessin(10.5, 5.5)

    etab_cell = Paragraph(_tronquer(nom_etab, 45), s_etab)
    gauche_cell = armoirie_img if armoirie_img else Paragraph("", s_etab)
    droite_cell = drapeau_img if drapeau_img else Paragraph("", s_etab)

    bandeau_etab = Table(
        [[gauche_cell, etab_cell, droite_cell]],
        colWidths=[10 * mm, L_utile - 22.5 * mm, 12.5 * mm],
        rowHeights=[6.2 * mm],
    )
    bandeau_etab.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLEU_CLAIR),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    titre_carte = Table(
        [[Paragraph("CARTE D'IDENTITÉ SCOLAIRE", s_titre_carte)]],
        colWidths=[L_utile],
        rowHeights=[4.3 * mm],
    )
    titre_carte.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BLEU_MARINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    bandeau_annee = Table(
        [[Paragraph(f"Année scolaire : {annee_libelle}", s_annee)]],
        colWidths=[L_utile],
        rowHeights=[4.0 * mm],
    )
    bandeau_annee.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), JAUNE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # ---- CORPS ----
    PHOTO_W = 21 * mm
    INFOS_W = 46 * mm
    QR_W    = 16.6 * mm

    photo_w, photo_h = 18 * mm, 22 * mm
    if eleve.photo:
        try:
            photo_cell = RLImage(eleve.photo.path, width=photo_w, height=photo_h)
        except Exception:
            photo_cell = Paragraph(
                "<para align='center'><font size=5 color='#94A3B8'>Photo</font></para>",
                s_valeur)
    else:
        photo_cell = Paragraph(
            "<para align='center'><font size=5 color='#94A3B8'>Photo</font></para>",
            s_valeur)

    sig_img_small = None
    if config and config.signature_chef:
        try:
            sig_img_small = RLImage(config.signature_chef.path,
                                    width=20 * mm, height=6 * mm)
        except Exception:
            sig_img_small = None

    cachet_img_overlay = None
    if config and config.cachet_ecole:
        try:
            cachet_img_overlay = RLImage(config.cachet_ecole.path,
                                         width=11 * mm, height=11 * mm)
        except Exception:
            cachet_img_overlay = None

    if cachet_img_overlay:
        zone_bas = Table(
            [[sig_img_small if sig_img_small else "", cachet_img_overlay]],
            colWidths=[13 * mm, 8 * mm],
            rowHeights=[15 * mm],
        )
        zone_bas.setStyle(TableStyle([
            ('VALIGN', (0, 0), (0, 0), 'BOTTOM'),
            ('VALIGN', (1, 0), (1, 0), 'TOP'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
    else:
        zone_bas = Table(
            [[sig_img_small if sig_img_small else ""]],
            colWidths=[21 * mm],
            rowHeights=[15 * mm],
        )
        zone_bas.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

    bloc_gauche = Table(
        [[photo_cell],
         [zone_bas]],
        colWidths=[21 * mm],
        rowHeights=[22 * mm, 15 * mm],
    )
    bloc_gauche.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
        ('VALIGN', (0, 1), (0, 1), 'TOP'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 1), (0, 1), -8 * mm),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    def ligne(label, valeur, vs=None):
        return [Paragraph(f"{label} :", s_label), Paragraph(valeur, vs or s_valeur)]

    infos_data = [
        ligne("Matricule", _valeur(eleve.matricule), s_valeur_rouge),
        ligne("Nom", _tronquer((eleve.nom or "").upper(), 18)),
        ligne("Prénom(s)", _tronquer(eleve.prenom or "", 18)),
        ligne("Né(e) le", _fmt_date(eleve.date_naissance)),
        ligne("À", _tronquer(
            (_valeur(eleve.lieu_naissance, "") +
             (" / " + eleve.get_prefecture_naissance_display() if eleve.prefecture_naissance else "")
            ).strip(" /") or "—",
            20
        )),
        ligne("Sexe", eleve.get_sexe_display() if eleve.sexe else "—"),
        ligne("Classe", _valeur(classe.nom if classe else "—")),
    ]

    infos_table = Table(infos_data, colWidths=[15 * mm, 31 * mm])
    infos_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 0.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
    ]))

    qr_data = f"{eleve.matricule}|{eleve.nom} {eleve.prenom}|{nom_etab}|{annee_libelle}"
    qr_img = _generer_qr_code(qr_data, taille_mm=14) or Paragraph("", s_valeur)

    bloc_infos_qr = Table(
        [[infos_table, qr_img]],
        colWidths=[INFOS_W, QR_W],
        rowHeights=[22 * mm],
    )
    bloc_infos_qr.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
        ('VALIGN', (1, 0), (1, 0), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (1, 0), (1, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    corps = Table(
        [[bloc_gauche, bloc_infos_qr]],
        colWidths=[PHOTO_W, L_utile - PHOTO_W],
        rowHeights=[26 * mm],
    )
    corps.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
        ('VALIGN', (1, 0), (1, 0), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (0, 0), 1),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('LEFTPADDING', (1, 0), (1, 0), 3.5 * mm),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # ---- Pied ----
    nom_chef = ""
    if config and config.nom_chef:
        nom_chef = config.nom_chef
    if not nom_chef and classe and getattr(classe, 'titulaire', None) and classe.titulaire.user:
        nom_chef = classe.titulaire.user.get_full_name() or classe.titulaire.user.username

    titre_chef = ""
    if config and config.titre_chef:
        titre_chef = config.titre_chef

    ville = "—"
    if config:
        ville = (config.ville_document or "").strip() or (config.commune or "").strip() or "—"
    date_sign = datetime.now().strftime('%d/%m/%Y')
    fait_a_txt = f"Fait à {ville}, le {date_sign}"

    tel_directeur = etablissement.telephone or ""
    tel_txt = f"Tél : {tel_directeur}" if tel_directeur else ""

    nom_titre_stack = Table(
        [[Paragraph(_tronquer(nom_chef, 20), s_pied_chef)],
         [Paragraph(titre_chef, s_pied_titre) if titre_chef else Paragraph("", s_pied_titre)]],
        colWidths=[20 * mm],
        rowHeights=[3.5 * mm, 3.5 * mm],
    )
    nom_titre_stack.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    ligne_pied = Table(
        [[
            nom_titre_stack,
            '',
            Paragraph(tel_txt, s_pied_tel),
            Paragraph(fait_a_txt, s_pied_fait),
        ]],
        colWidths=[20 * mm, 15 * mm, 20 * mm, L_utile - 55 * mm],
        rowHeights=[7 * mm],
    )
    ligne_pied.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('ALIGN', (2, 0), (2, 0), 'LEFT'),
        ('ALIGN', (3, 0), (3, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (0, 0), 2),
        ('RIGHTPADDING', (0, 0), (0, 0), 1),
        ('LEFTPADDING', (1, 0), (1, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('LEFTPADDING', (2, 0), (2, 0), 1),
        ('RIGHTPADDING', (2, 0), (2, 0), 1),
        ('LEFTPADDING', (3, 0), (3, 0), 1),
        ('RIGHTPADDING', (3, 0), (3, 0), 3 * mm),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    h_ligne = 7 * mm
    pied = Table(
        [[ligne_pied]],
        colWidths=[L_utile],
        rowHeights=[h_ligne],
    )
    pied.setStyle(TableStyle([
        ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # ---- Assemblage ----
    h_bandeau_pays = 5.8 * mm
    h_bandeau_etab = 6.2 * mm
    h_titre_carte  = 4.3 * mm
    h_annee        = 4.0 * mm
    h_corps        = 26.7 * mm
    h_pied_total   = h_ligne

    contenu_carte = Table(
        [[bandeau_pays], [bandeau_etab], [titre_carte],
         [bandeau_annee], [corps], [pied]],
        colWidths=[L_utile],
        rowHeights=[h_bandeau_pays, h_bandeau_etab, h_titre_carte,
                    h_annee, h_corps, h_pied_total],
    )
    contenu_carte.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    PADDING_INTERNE = 0.5 * mm

    carte_finale = Table([[contenu_carte]], colWidths=[CARTE_L], rowHeights=[CARTE_H])
    carte_finale.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), BORDURE_CARTE_MM, BLEU_MARINE),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ('LEFTPADDING', (0, 0), (-1, -1), PADDING_INTERNE),
        ('RIGHTPADDING', (0, 0), (-1, -1), PADDING_INTERNE),
        ('TOPPADDING', (0, 0), (-1, -1), PADDING_INTERNE),
        ('BOTTOMPADDING', (0, 0), (-1, -1), PADDING_INTERNE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    cachet_info = {'path': None, 'taille_mm': 11}
    return carte_finale, cachet_info


# =====================================================
# FONCTION PUBLIQUE
# =====================================================
def exporter_cartes_scolaires_pdf(eleves_data, annee_libelle, config=None,
                                   utilisateur=None):
    """Génère un PDF A4 contenant 10 cartes par page (2×5)."""
    output = BytesIO()

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=MARGE_PAGE, rightMargin=MARGE_PAGE,
        topMargin=MARGE_PAGE, bottomMargin=MARGE_PAGE,
    )

    def page_vide(canvas, doc_):
        pass

    doc.onFirstPage = page_vide
    doc.onLaterPages = page_vide

    elements = []

    etablissement = None
    if config and config.etablissement:
        etablissement = config.etablissement
    elif eleves_data:
        etablissement = eleves_data[0]['eleve'].etablissement

    cartes = []
    for item in eleves_data:
        carte_tbl, cachet_info = _construire_carte(
            item['eleve'], item['classe'], annee_libelle, config, etablissement
        )
        cartes.append((carte_tbl, cachet_info))

    cartes_par_page = COLS * ROWS
    total_pages = (len(cartes) + cartes_par_page - 1) // cartes_par_page if cartes else 0

    for page_idx in range(total_pages):
        debut = page_idx * cartes_par_page
        fin = min(debut + cartes_par_page, len(cartes))
        page_items = cartes[debut:fin]

        while len(page_items) < cartes_par_page:
            page_items.append((Spacer(CARTE_L, CARTE_H), None))

        lignes_avec_gap = []
        for r in range(ROWS):
            ligne_cartes = []
            for c in range(COLS):
                idx = r * COLS + c
                ligne_cartes.append(page_items[idx][0])
                if c < COLS - 1:
                    ligne_cartes.append('')
            lignes_avec_gap.append(ligne_cartes)

            if r < ROWS - 1:
                ligne_sep = []
                for c in range(COLS):
                    ligne_sep.append('')
                    if c < COLS - 1:
                        ligne_sep.append('')
                lignes_avec_gap.append(ligne_sep)

        largeurs_col = []
        for c in range(COLS):
            largeurs_col.append(CARTE_L)
            if c < COLS - 1:
                largeurs_col.append(GAP_X)

        hauteurs_row = []
        for r in range(ROWS):
            hauteurs_row.append(CARTE_H)
            if r < ROWS - 1:
                hauteurs_row.append(GAP_Y)

        grille = Table(
            lignes_avec_gap,
            colWidths=largeurs_col,
            rowHeights=hauteurs_row,
            hAlign='CENTER',
        )
        grille.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))

        elements.append(grille)
        if page_idx < total_pages - 1:
            elements.append(PageBreak())

    if elements:
        doc.build(elements)

    output.seek(0)
    return output
