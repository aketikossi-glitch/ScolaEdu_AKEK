"""
Module de génération de l'en-tête officiel des documents scolaires togolais.
Version 12 : armoirie à taille bornée (ratio préservé) + colonne centrale élargie.
"""
import os
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    Table, TableStyle, Paragraph, Spacer, Image as RLImage
)

DEFAUTS = {
    'ministere': "MINISTÈRE DE L'ÉDUCATION NATIONALE",
    'direction_regionale': 'DRE-PLATEAUX',
    'inspection': 'IESG-NOTSE',
    'pays': 'RÉPUBLIQUE TOGOLAISE',
    'devise_nationale': 'Travail - Liberté - Patrie',
}


# =========================================================
# Helper : taille d'image bornée (ratio préservé)
# =========================================================
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


def generer_entete_document(config=None, armoirie_path=None, style='complet', orientation='portrait'):
    """
    En-tête officiel : blocs poussés aux extrémités.
    Version 12 : armoirie bornée 20×20mm, ratio préservé, colonne centrale 26mm.
    """
    from django.conf import settings

    styles = getSampleStyleSheet()

    if orientation == 'paysage':
        largeur_page_cm = 29.7
        taille_police = 9
        taille_police_ecole = 10
        # Bornes max de la boîte contenant l'armoirie
        max_armoirie_largeur_mm = 24
        max_armoirie_hauteur_mm = 24
    else:
        largeur_page_cm = 21.0
        taille_police = 7.5
        taille_police_ecole = 8.5
        max_armoirie_largeur_mm = 20
        max_armoirie_hauteur_mm = 20

    gauche_style = ParagraphStyle(
        'Gauche', parent=styles['Normal'],
        alignment=1,
        fontSize=taille_police, leading=taille_police + 1.5,
        textColor=colors.HexColor('#000000'),  # NOIR_ENTETE_PATCH
    )
    droite_style = ParagraphStyle(
        'Droite', parent=styles['Normal'],
        alignment=1,
        fontSize=taille_police, leading=taille_police + 1.5,
        textColor=colors.HexColor('#000000'),  # NOIR_ENTETE_PATCH
    )

    # =========================================================
    # Valeurs
    # =========================================================
    if config:
        ministere = config.ministere or DEFAUTS['ministere']
        direction = config.direction_regionale or DEFAUTS['direction_regionale']
        inspection = config.inspection or DEFAUTS['inspection']
        pays = DEFAUTS['pays']
        devise = config.devise_nationale or DEFAUTS['devise_nationale']
    else:
        ministere = DEFAUTS['ministere']
        direction = DEFAUTS['direction_regionale']
        inspection = DEFAUTS['inspection']
        pays = DEFAUTS['pays']
        devise = DEFAUTS['devise_nationale']

    # ✅ Récupérer infos établissement (nom, BP, tel)
    etablissement_nom = ""
    etablissement_telephone = ""
    etablissement_bp = ""

    if config and config.etablissement:
        etab = config.etablissement
        etablissement_nom = (etab.nom or "").upper()
        etablissement_telephone = etab.telephone or ""
        etablissement_bp = getattr(etab, 'bp', '') or ""

    # =========================================================
    # Bloc GAUCHE
    # =========================================================
    gauche_parts = [
        f"<b>{ministere}</b>",
        direction,
        inspection,
        '<font size="6">— ● —</font>',
    ]

    if etablissement_nom:
        gauche_parts.append(f"<b>{etablissement_nom}</b>")

    # ✅ BP + Tel sur la même ligne
    coord_parts = []
    if etablissement_bp:
        coord_parts.append(f"BP : {etablissement_bp}")
    if etablissement_telephone:
        coord_parts.append(f"Tel : {etablissement_telephone}")

    if coord_parts:
        gauche_parts.append("&nbsp;&nbsp;/&nbsp;&nbsp;".join(coord_parts))

    gauche_html = "<br/>".join(gauche_parts)

    droite_html = f"<b>{pays}</b><br/><i>{devise}</i>"

    # =========================================================
    # Armoirie (taille bornée 20×20mm, ratio préservé)
    # =========================================================
    armoirie_img = None
    if style == 'complet':
        if not armoirie_path:
            path1 = os.path.join(settings.BASE_DIR, 'static', 'images', 'armoiries_togo.png')
            if config and config.etablissement and config.etablissement.logo:
                try:
                    path2 = config.etablissement.logo.path
                    if os.path.exists(path2) and os.path.getsize(path2) > 0:
                        armoirie_path = path2
                except Exception:
                    pass
            if not armoirie_path and os.path.exists(path1) and os.path.getsize(path1) > 0:
                armoirie_path = path1

        if armoirie_path and os.path.exists(armoirie_path) and os.path.getsize(armoirie_path) > 0:
            try:
                w_mm, h_mm = _calc_logo_size_mm(
                    armoirie_path,
                    max_armoirie_largeur_mm,
                    max_armoirie_hauteur_mm,
                )
                armoirie_img = RLImage(
                    armoirie_path,
                    width=w_mm * mm,
                    height=h_mm * mm,
                )
            except Exception:
                armoirie_img = None

    largeur_dispo = largeur_page_cm * cm - 4 * mm
    largeur_centre = 26 * mm  # ✅ élargie de 2mm → 26mm
    largeur_bloc = (largeur_dispo - largeur_centre) / 2

    if armoirie_img:
        conteneur_data = [[
            Paragraph(gauche_html, gauche_style),
            armoirie_img,
            Paragraph(droite_html, droite_style),
        ]]
    else:
        conteneur_data = [[
            Paragraph(gauche_html, gauche_style),
            '',
            Paragraph(droite_html, droite_style),
        ]]

    conteneur = Table(
        conteneur_data,
        colWidths=[largeur_bloc, largeur_centre, largeur_bloc],
        rowHeights=[24 * mm],
    )
    conteneur.setStyle(TableStyle([
        # ✅ VALIGN_PATCH_NOIR — Gauche/Droite en haut, armoirie centrée
        ('VALIGN', (0, 0), (0, 0), 'TOP'),
        ('VALIGN', (1, 0), (1, 0), 'MIDDLE'),
        ('VALIGN', (2, 0), (2, 0), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    elements = [
        conteneur,
        Spacer(1, 1*mm),
    ]

    return elements


def generer_entete_simple(config=None, orientation='portrait'):
    return generer_entete_document(config, style='simple', orientation=orientation)


def generer_entete_complet(config=None, orientation='portrait'):
    return generer_entete_document(config, style='complet', orientation=orientation)
