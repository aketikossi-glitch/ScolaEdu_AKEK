"""
Fonctions utilitaires pour le traitement des images.
Version corrigée avec gestion d'erreurs visible.
"""
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys
import logging

logger = logging.getLogger(__name__)


def traiter_photo_passeport(image_field, largeur_mm=35, hauteur_mm=45, dpi=300):
    """
    Recadre et redimensionne une photo au format passeport (3.5 x 4.5 cm).
    Retourne un InMemoryUploadedFile OU None en cas d'échec.
    """
    if not image_field:
        return None

    try:
        img = Image.open(image_field)
        logger.info(f"Photo ouverte : {img.size} mode={img.mode}")
    except Exception as e:
        logger.error(f"Erreur ouverture photo : {e}")
        return image_field  # Retourner l'original si erreur

    try:
        # Convertir en RGB (supprime transparence)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # Dimensions cibles (35x45 mm à 300 dpi)
        largeur_px = int(largeur_mm / 25.4 * dpi)   # ~413 px
        hauteur_px = int(hauteur_mm / 25.4 * dpi)   # ~531 px

        # Recadrage centré
        img_ratio = img.width / img.height
        cible_ratio = largeur_px / hauteur_px

        if img_ratio > cible_ratio:
            new_width = int(img.height * cible_ratio)
            offset = (img.width - new_width) // 2
            img = img.crop((offset, 0, offset + new_width, img.height))
        else:
            new_height = int(img.width / cible_ratio)
            offset = max(0, (img.height - new_height) // 4)
            img = img.crop((0, offset, img.width, offset + new_height))

        # Redimensionner
        img = img.resize((largeur_px, hauteur_px), Image.LANCZOS)

        # Sauvegarder en mémoire
        output = BytesIO()
        img.save(output, format='JPEG', quality=92, optimize=True)
        output.seek(0)

        nom_fichier = getattr(image_field, 'name', 'photo.jpg')
        if not nom_fichier.lower().endswith(('.jpg', '.jpeg')):
            nom_fichier = nom_fichier.rsplit('.', 1)[0] + '.jpg'

        result = InMemoryUploadedFile(
            output,
            'ImageField',
            nom_fichier,
            'image/jpeg',
            sys.getsizeof(output),
            None
        )
        logger.info(f"Photo traitée avec succès : {largeur_px}x{hauteur_px}")
        return result

    except Exception as e:
        logger.error(f"Erreur traitement photo : {e}")
        return image_field  # Retourner l'original si erreur
