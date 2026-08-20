from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PortfolioEvidenceCreate(BaseModel):
    """§17 cahier fonctionnel : contexte, problème, rôle, livrable, résultat,
    métriques, compétences associées. L'objectif est de démontrer une
    compétence, pas seulement de signaler qu'un cours a été terminé."""
    title: str = Field(min_length=1, max_length=200)
    context: str | None = None
    problem: str | None = None
    role: str | None = None
    deliverable: str | None = None
    result: str | None = None
    metrics: dict | None = None
    skill_ids: list[str] = []


class PortfolioEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    context: str | None = None
    problem: str | None = None
    role: str | None = None
    deliverable: str | None = None
    result: str | None = None
    metrics: dict | None = None
    feedback: str | None = None
    skill_ids: list[str] = []
    created_at: datetime
    updated_at: datetime
