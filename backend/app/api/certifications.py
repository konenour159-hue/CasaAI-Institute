"""
Endpoints certifications (§18 cahier fonctionnel). Le catalogue est public
(comme les cours/parcours/labs) ; l'évaluation d'éligibilité est authentifiée
puisqu'elle porte sur la progression d'un utilisateur précis.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.certification_repository import CertificationRepository
from app.schemas.certification import (
    CertificationDetailOut,
    CertificationEligibilityOut,
    CertificationListOut,
    CertificationRequirementOut,
    CourseCertificateEligibilityOut,
    CourseCertificateOut,
)
from app.services.certification_service import CertificationService
from app.services.course_certificate_service import CourseCertificateService, CourseNotFoundError, NotEligibleError

router = APIRouter(prefix="/api", tags=["certifications"])


@router.get("/certifications", response_model=list[CertificationListOut])
def list_certifications(db: Session = Depends(get_db)) -> list[CertificationListOut]:
    items = CertificationRepository(db).list_certifications()
    return [CertificationListOut.model_validate(c) for c in items]


@router.get("/certifications/{certification_id}", response_model=CertificationDetailOut)
def get_certification(certification_id: str, db: Session = Depends(get_db)) -> CertificationDetailOut:
    cert = CertificationRepository(db).get_certification(certification_id)
    if cert is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification introuvable.")
    return CertificationDetailOut(
        **CertificationListOut.model_validate(cert).model_dump(),
        requirements=[
            CertificationRequirementOut(
                id=str(r.id), requirement_type=r.requirement_type.value, description=r.description,
                course_id=r.course_id, lab_id=r.lab_id, skill_id=r.skill_id, min_score=r.min_score,
            )
            for r in cert.requirements
        ],
    )


@router.get("/me/certifications/{certification_id}/eligibility", response_model=CertificationEligibilityOut)
def get_my_eligibility(
    certification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CertificationEligibilityOut:
    result = CertificationService(db).evaluate_eligibility(current_user.id, certification_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certification introuvable.")
    return result


# --- Certificat de module (par cours, basé sur les quiz) -------------------

@router.get("/courses/{course_id}/certificate/eligibility", response_model=CourseCertificateEligibilityOut)
def get_course_certificate_eligibility(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CourseCertificateEligibilityOut:
    try:
        return CourseCertificateService(db).get_eligibility(current_user.id, course_id)
    except CourseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/courses/{course_id}/certificate", response_model=CourseCertificateOut)
def issue_course_certificate(
    course_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CourseCertificateOut:
    try:
        cert = CourseCertificateService(db).issue_certificate(current_user.id, course_id)
    except CourseNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except NotEligibleError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return CourseCertificateOut.model_validate(cert)


@router.get("/me/course-certificates", response_model=list[CourseCertificateOut])
def list_my_course_certificates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CourseCertificateOut]:
    certs = CertificationRepository(db).list_my_course_certificates(current_user.id)
    return [CourseCertificateOut.model_validate(c) for c in certs]
