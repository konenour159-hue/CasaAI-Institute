"""
Endpoints admin — édition des critères de certification. Réservés à
SUPER_ADMIN (require_super_admin), même périmètre que la gestion des
utilisateurs et de la progression globale (cf. app/api/deps.py).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.session import get_db
from app.models.user import User
from app.repositories.admin_certification_repository import AdminCertificationRepository
from app.schemas.admin import (
    AdminCertificationListItemOut,
    AdminCertificationListResponse,
    AdminCertificationOut,
    AdminCertificationRequirementIn,
    AdminCertificationRequirementOut,
)
from app.services.admin_certification_service import (
    AdminCertificationService,
    CertificationNotFoundError,
    RequirementNotFoundError,
    ValidationError,
)

router = APIRouter(prefix="/api/admin/certifications", tags=["admin-certifications"])


@router.get("", response_model=AdminCertificationListResponse)
def admin_list_certifications(
    db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)
) -> AdminCertificationListResponse:
    rows = AdminCertificationRepository(db).list_certifications()
    return AdminCertificationListResponse(
        items=[
            AdminCertificationListItemOut(
                id=c.id, title=c.title, level=c.level, status=c.status,
                requirement_count=total, linked_requirement_count=linked,
            )
            for c, total, linked in rows
        ]
    )


@router.get("/{certification_id}", response_model=AdminCertificationOut)
def admin_get_certification(
    certification_id: str, db: Session = Depends(get_db), _admin: User = Depends(require_super_admin)
) -> AdminCertificationOut:
    cert = AdminCertificationRepository(db).get_certification_any_status(certification_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification introuvable.")
    return AdminCertificationOut(
        id=cert.id, title=cert.title, level=cert.level, description=cert.description, status=cert.status,
        requirements=[AdminCertificationRequirementOut.model_validate(r) for r in cert.requirements],
    )


@router.put("/{certification_id}/requirements/{requirement_id}", response_model=AdminCertificationRequirementOut)
def admin_update_certification_requirement(
    certification_id: str,
    requirement_id: uuid.UUID,
    payload: AdminCertificationRequirementIn,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_super_admin),
) -> AdminCertificationRequirementOut:
    try:
        requirement = AdminCertificationService(db).update_requirement(certification_id, requirement_id, payload)
    except (CertificationNotFoundError, RequirementNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
    return AdminCertificationRequirementOut.model_validate(requirement)
