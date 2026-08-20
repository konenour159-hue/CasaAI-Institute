"""
Upload d'images pour les sections de leçon (formulaire admin « Ajouter un
cours » / édition de leçon). Réservé au rôle ADMIN (cf. api/deps.py).

Volontairement découplé du lesson_id / section_id : le formulaire d'édition
de leçon (AdminLessonEditPage) remplace intégralement ses sections à chaque
enregistrement (voir repositories/admin_content_repository._replace_nested),
y compris pour des sections pas encore persistées (nouvelle leçon, nouvelle
section). On ne peut donc pas router l'upload par un ID de section stable.
Le flux est : l'admin choisit une image → upload immédiat vers cet endpoint
→ l'URL retournée est stockée dans l'état local du formulaire → elle voyage
comme un champ normal (image_url) dans le payload au moment d'« Enregistrer
la leçon », exactement comme title/body aujourd'hui.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import require_content_admin
from app.models.user import User
from app.schemas.admin import MediaUploadOut
from app.services.storage_service import (
    FileTooLargeError,
    InvalidImageError,
    UnsupportedMediaTypeError,
    get_storage_service,
)

router = APIRouter(prefix="/api/admin/media", tags=["admin-media"])


@router.post("/images", response_model=MediaUploadOut, status_code=status.HTTP_201_CREATED)
async def admin_upload_section_image(
    file: UploadFile = File(...),
    _admin: User = Depends(require_content_admin),
) -> MediaUploadOut:
    file_bytes = await file.read()
    storage = get_storage_service()
    try:
        url, size_bytes = storage.save_image(file_bytes, file.content_type or "")
    except UnsupportedMediaTypeError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    except FileTooLargeError as e:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(e))
    except InvalidImageError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))

    return MediaUploadOut(url=url, content_type=file.content_type or "", size_bytes=size_bytes)
