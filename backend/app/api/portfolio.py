"""
Endpoints du portfolio de preuves (§17 cahier fonctionnel). Toutes
authentifiées ; un apprenant ne voit et ne modifie que ses propres preuves.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.repositories.portfolio_repository import PortfolioRepository
from app.schemas.portfolio import PortfolioEvidenceCreate, PortfolioEvidenceOut

router = APIRouter(prefix="/api", tags=["portfolio"])


def _to_out(evidence, skill_ids: list[str]) -> PortfolioEvidenceOut:
    return PortfolioEvidenceOut(
        id=evidence.id, title=evidence.title, context=evidence.context, problem=evidence.problem,
        role=evidence.role, deliverable=evidence.deliverable, result=evidence.result,
        metrics=evidence.metrics, feedback=evidence.feedback, skill_ids=skill_ids,
        created_at=evidence.created_at, updated_at=evidence.updated_at,
    )


@router.post("/portfolio/evidence", response_model=PortfolioEvidenceOut, status_code=status.HTTP_201_CREATED)
def create_evidence(
    payload: PortfolioEvidenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioEvidenceOut:
    repo = PortfolioRepository(db)
    evidence, skill_ids = repo.create(
        user_id=current_user.id, title=payload.title, context=payload.context, problem=payload.problem,
        role=payload.role, deliverable=payload.deliverable, result=payload.result,
        metrics=payload.metrics, skill_ids=payload.skill_ids,
    )
    db.commit()
    db.refresh(evidence)
    return _to_out(evidence, skill_ids)


@router.get("/me/portfolio", response_model=list[PortfolioEvidenceOut])
def list_my_portfolio(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PortfolioEvidenceOut]:
    rows = PortfolioRepository(db).list_for_user(current_user.id)
    return [_to_out(e, skill_ids) for e, skill_ids in rows]


@router.get("/portfolio/evidence/{evidence_id}", response_model=PortfolioEvidenceOut)
def get_evidence(
    evidence_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PortfolioEvidenceOut:
    result = PortfolioRepository(db).get_for_user(current_user.id, evidence_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preuve introuvable.")
    evidence, skill_ids = result
    return _to_out(evidence, skill_ids)
