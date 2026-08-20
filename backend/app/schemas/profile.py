"""
Profil d'onboarding de l'apprenant (persona, objectifs de carrière,
objectifs, compétences déjà acquises) — modèle `UserProfile` rempli à
l'inscription mais jusqu'ici jamais exposé par l'API (cf. audit du site).

`theme`/`reduced_motion`/`language` existent sur le modèle mais ne sont
volontairement pas exposés ici : aucune de ces trois préférences n'a
d'effet réel sur le comportement du site aujourd'hui (pas de bascule de
thème, pas d'i18n, `prefers-reduced-motion` déjà géré au niveau du système
d'exploitation) — les exposer donnerait l'illusion d'un réglage qui ne fait
rien.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class UserProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    profile_type_id: str | None = None
    level: str | None = None
    career_objectives: str | None = None
    onboarding_done: bool
    goal_ids: list[str] = Field(default_factory=list)
    interest_skill_ids: list[str] = Field(default_factory=list)


class UserProfileUpdateRequest(BaseModel):
    """Remplacement intégral (mêmes conventions que PUT /api/admin/lessons/{id})
    — plus simple à raisonner qu'un patch partiel pour un formulaire qui
    soumet toujours l'état complet du profil."""
    profile_type_id: str | None = None
    level: str | None = Field(default=None, max_length=100)
    career_objectives: str | None = Field(default=None, max_length=2000)
    goal_ids: list[str] = Field(default_factory=list)
    interest_skill_ids: list[str] = Field(default_factory=list)
