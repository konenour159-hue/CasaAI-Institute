from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.repositories.user_profile_repository import UserProfileRepository
from app.schemas.profile import UserProfileOut, UserProfileUpdateRequest


class UserProfileService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UserProfileRepository(db)

    def get_profile(self, user_id: uuid.UUID) -> UserProfileOut:
        profile = self.repo.get_by_user_id(user_id)
        if profile is None:
            # Pas encore d'onboarding rempli — un état vide plutôt qu'un 404 :
            # ce n'est pas une erreur, juste un profil qui reste à compléter.
            return UserProfileOut(profile_type_id=None, level=None, career_objectives=None, onboarding_done=False)
        return UserProfileOut(
            profile_type_id=profile.profile_type_id,
            level=profile.level,
            career_objectives=profile.career_objectives,
            onboarding_done=profile.onboarding_done,
            goal_ids=self.repo.get_goal_ids(user_id),
            interest_skill_ids=self.repo.get_interest_skill_ids(user_id),
        )

    def update_profile(self, user_id: uuid.UUID, payload: UserProfileUpdateRequest) -> UserProfileOut:
        self.repo.upsert(
            user_id,
            profile_type_id=payload.profile_type_id,
            level=payload.level,
            career_objectives=payload.career_objectives,
            goal_ids=payload.goal_ids,
            interest_skill_ids=payload.interest_skill_ids,
        )
        self.db.commit()
        return self.get_profile(user_id)
