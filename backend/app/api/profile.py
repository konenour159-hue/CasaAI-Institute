"""
Profil d'onboarding de l'apprenant (persona, objectifs de carrière, objectifs,
compétences déjà acquises) — cf. app/schemas/profile.py pour le contexte :
ces données étaient collectées à l'inscription mais jamais exposées.

    GET /api/me/onboarding-profile
    PUT /api/me/onboarding-profile
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.profile import UserProfileOut, UserProfileUpdateRequest
from app.services.user_profile_service import UserProfileService

router = APIRouter(prefix="/api/me", tags=["profile"])


@router.get("/onboarding-profile", response_model=UserProfileOut)
def get_my_onboarding_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileOut:
    return UserProfileService(db).get_profile(current_user.id)


@router.put("/onboarding-profile", response_model=UserProfileOut)
def update_my_onboarding_profile(
    payload: UserProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserProfileOut:
    return UserProfileService(db).update_profile(current_user.id, payload)
