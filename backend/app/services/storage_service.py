"""
Stockage des fichiers médias (images de sections de leçon, § éditeur admin).

MVP : disque local, servi en statique par FastAPI (app.mount dans main.py).
Le cahier technique (§10) anticipe un stockage objet S3-compatible (MinIO en
local, cf. settings.storage_endpoint / storage_bucket) : cette classe isole
volontairement la logique de stockage derrière une interface simple
(save_image / delete_image) pour permettre de remplacer l'implémentation par
un client boto3/MinIO plus tard sans toucher aux routes ni au modèle de
données. Les URLs retournées à l'appelant sont opaques : rien côté appelant
ne suppose qu'elles pointent vers le disque local.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path

from app.core.config import settings


class UnsupportedMediaTypeError(Exception):
    pass


class FileTooLargeError(Exception):
    pass


class InvalidImageError(Exception):
    pass


_EXTENSION_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class LocalStorageService:
    """Implémentation disque local. Écrit sous MEDIA_ROOT/sections/<uuid><ext>
    et renvoie une URL relative servie par le mount StaticFiles de main.py."""

    def __init__(self) -> None:
        self._root = Path(settings.media_root)

    def _validate(self, content_type: str, file_bytes: bytes) -> None:
        if content_type not in settings.media_allowed_content_types:
            raise UnsupportedMediaTypeError(
                f"Type de fichier non supporté : {content_type}. "
                f"Formats acceptés : {', '.join(settings.media_allowed_content_types)}."
            )
        max_bytes = settings.media_max_upload_mb * 1024 * 1024
        if len(file_bytes) > max_bytes:
            raise FileTooLargeError(
                f"Fichier trop volumineux ({len(file_bytes) / 1024 / 1024:.1f} Mo). "
                f"Maximum : {settings.media_max_upload_mb} Mo."
            )
        # Vérifie que le contenu est réellement une image décodable (et pas
        # un fichier renommé avec une extension/Content-Type trompeur) —
        # Pillow lève une exception sur un flux non-image.
        try:
            from PIL import Image  # import différé : dépendance dédiée à cette validation

            with Image.open(io.BytesIO(file_bytes)) as img:
                img.verify()
        except Exception as e:
            raise InvalidImageError("Le fichier fourni n'est pas une image valide.") from e

    def save_image(self, file_bytes: bytes, content_type: str) -> tuple[str, int]:
        """Valide et enregistre l'image. Retourne (url_publique, taille_octets)."""
        self._validate(content_type, file_bytes)

        subdir = self._root / "sections"
        subdir.mkdir(parents=True, exist_ok=True)

        ext = _EXTENSION_BY_CONTENT_TYPE[content_type]
        filename = f"{uuid.uuid4()}{ext}"
        (subdir / filename).write_bytes(file_bytes)

        url = f"{settings.media_public_base_url}/sections/{filename}"
        return url, len(file_bytes)

    def delete_image(self, url: str) -> None:
        """Best-effort : ne lève pas si le fichier n'existe pas/plus, pour
        rester idempotent (une section peut référencer une image déjà purgée)."""
        if not url.startswith(settings.media_public_base_url):
            return
        relative = url[len(settings.media_public_base_url):].lstrip("/")
        path = self._root / relative
        path.unlink(missing_ok=True)


def get_storage_service() -> LocalStorageService:
    """Point d'extension unique : basculer vers un backend S3/MinIO revient à
    retourner une autre implémentation ici (même interface save_image/delete_image)."""
    return LocalStorageService()
