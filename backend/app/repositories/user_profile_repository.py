from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import UserProfile, user_profile_goals, user_profile_interest_skills


class UserProfileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: uuid.UUID) -> UserProfile | None:
        return self.db.get(UserProfile, user_id)

    def get_goal_ids(self, user_id: uuid.UUID) -> list[str]:
        return list(
            self.db.execute(
                select(user_profile_goals.c.goal_id).where(user_profile_goals.c.user_id == user_id)
            ).scalars()
        )

    def get_interest_skill_ids(self, user_id: uuid.UUID) -> list[str]:
        return list(
            self.db.execute(
                select(user_profile_interest_skills.c.skill_id).where(
                    user_profile_interest_skills.c.user_id == user_id
                )
            ).scalars()
        )

    def upsert(
        self, user_id: uuid.UUID, *, profile_type_id: str | None, level: str | None,
        career_objectives: str | None, goal_ids: list[str], interest_skill_ids: list[str],
    ) -> UserProfile:
        profile = self.get_by_user_id(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self.db.add(profile)

        profile.profile_type_id = profile_type_id
        profile.level = level
        profile.career_objectives = career_objectives
        profile.onboarding_done = True

        # Association simple (pas de relationship ORM déclarée sur
        # UserProfile, cf. models/user.py) : on resynchronise en supprimant
        # puis réinsérant, plus simple à raisonner qu'un diff pour des
        # listes courtes soumises intégralement à chaque sauvegarde.
        self.db.execute(user_profile_goals.delete().where(user_profile_goals.c.user_id == user_id))
        self.db.execute(
            user_profile_interest_skills.delete().where(user_profile_interest_skills.c.user_id == user_id)
        )
        if goal_ids:
            self.db.execute(
                user_profile_goals.insert(),
                [{"user_id": user_id, "goal_id": gid} for gid in goal_ids],
            )
        if interest_skill_ids:
            self.db.execute(
                user_profile_interest_skills.insert(),
                [{"user_id": user_id, "skill_id": sid} for sid in interest_skill_ids],
            )

        self.db.flush()
        return profile
