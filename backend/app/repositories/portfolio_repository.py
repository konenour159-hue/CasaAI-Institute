from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.progress import PortfolioEvidence, portfolio_evidence_skills


class PortfolioRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, *, user_id: uuid.UUID, title: str, context: str | None, problem: str | None,
        role: str | None, deliverable: str | None, result: str | None, metrics: dict | None,
        skill_ids: list[str],
    ) -> tuple[PortfolioEvidence, list[str]]:
        evidence = PortfolioEvidence(
            user_id=user_id, title=title, context=context, problem=problem,
            role=role, deliverable=deliverable, result=result, metrics=metrics,
        )
        self.db.add(evidence)
        self.db.flush()
        for skill_id in skill_ids:
            self.db.execute(portfolio_evidence_skills.insert().values(evidence_id=evidence.id, skill_id=skill_id))
        self.db.flush()
        return evidence, skill_ids

    def list_for_user(self, user_id: uuid.UUID) -> list[tuple[PortfolioEvidence, list[str]]]:
        items = list(
            self.db.execute(
                select(PortfolioEvidence)
                .where(PortfolioEvidence.user_id == user_id)
                .order_by(PortfolioEvidence.created_at.desc())
            ).scalars()
        )
        return [(e, self._skill_ids(e.id)) for e in items]

    def get_for_user(self, user_id: uuid.UUID, evidence_id: uuid.UUID) -> tuple[PortfolioEvidence, list[str]] | None:
        evidence = self.db.execute(
            select(PortfolioEvidence).where(
                PortfolioEvidence.id == evidence_id, PortfolioEvidence.user_id == user_id
            )
        ).scalar_one_or_none()
        if evidence is None:
            return None
        return evidence, self._skill_ids(evidence.id)

    def _skill_ids(self, evidence_id: uuid.UUID) -> list[str]:
        return list(
            self.db.execute(
                select(portfolio_evidence_skills.c.skill_id).where(
                    portfolio_evidence_skills.c.evidence_id == evidence_id
                )
            ).scalars()
        )
