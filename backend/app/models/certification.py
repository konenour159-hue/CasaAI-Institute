from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, SmallInteger, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, uuid_pk
from app.models.content import CONTENT_STATUS_ENUM
from app.models.enums import CertificationRequirementType, ContentStatus, UserCertificationStatus


class Certification(Base, TimestampMixin):
    __tablename__ = "certifications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    level: Mapped[Optional[str]] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(String)
    color: Mapped[Optional[str]] = mapped_column(String)
    legacy_threshold: Mapped[Optional[int]] = mapped_column(SmallInteger)
    status: Mapped[ContentStatus] = mapped_column(CONTENT_STATUS_ENUM, nullable=False, default=ContentStatus.DRAFT)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    requirements: Mapped[list["CertificationRequirement"]] = relationship(
        back_populates="certification", order_by="CertificationRequirement.position", cascade="all, delete-orphan"
    )


class CertificationRequirement(Base):
    """Critères structurés définis par l'administrateur (§18 cahier fonctionnel) :
    cours requis, score minimum, labs requis, compétences requises, preuves
    requises, projet final. Chaque ligne est un critère atomique vérifiable."""
    __tablename__ = "certification_requirements"

    id: Mapped[uuid.UUID] = uuid_pk()
    certification_id: Mapped[str] = mapped_column(
        String, ForeignKey("certifications.id", ondelete="CASCADE"), nullable=False
    )
    requirement_type: Mapped[CertificationRequirementType] = mapped_column(
        Enum(CertificationRequirementType, name="certification_requirement_type"), nullable=False
    )
    course_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("courses.id", ondelete="CASCADE"))
    lab_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("labs.id", ondelete="CASCADE"))
    skill_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("skills.id", ondelete="CASCADE"))
    min_score: Mapped[Optional[int]] = mapped_column(SmallInteger)
    description: Mapped[Optional[str]] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    certification: Mapped["Certification"] = relationship(back_populates="requirements")


class UserCertification(Base):
    __tablename__ = "user_certifications"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    certification_id: Mapped[str] = mapped_column(
        String, ForeignKey("certifications.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[UserCertificationStatus] = mapped_column(
        Enum(UserCertificationStatus, name="user_certification_status"),
        nullable=False,
        default=UserCertificationStatus.IN_PROGRESS,
    )
    issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "certification_id", name="uq_user_certification"),)


class CourseCertificate(Base):
    """Certificat de module : délivré automatiquement à un apprenant quand la
    moyenne de ses meilleurs scores sur tous les quiz d'un cours atteint le
    seuil (cf. COURSE_CERTIFICATE_THRESHOLD, services/course_certificate_service.py).
    Distinct du catalogue `Certification` (parcours multi-cours, critères
    définis à la main par un administrateur) : ici l'éligibilité est
    entièrement dérivée des tentatives de quiz, un cours à la fois."""
    __tablename__ = "course_certificates"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    course_id: Mapped[str] = mapped_column(String, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    average_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_user_course_certificate"),)
