"""Tests sur /api/me/onboarding-profile — le modèle UserProfile était rempli
à l'inscription mais jamais exposé par l'API (cf. audit du site)."""
from __future__ import annotations

from app.models.catalog import School, Skill
from app.models.user import Goal, LearnerProfileType


def _register_and_login(client, email: str = "onboarding@example.com"):
    client.post(
        "/api/auth/register",
        json={"first_name": "Ada", "last_name": "Lovelace", "email": email, "password": "SuperSecret123!"},
    )
    login = client.post("/api/auth/login", json={"email": email, "password": "SuperSecret123!"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _seed_catalog(db_session):
    db_session.add(LearnerProfileType(id="test-persona", name="Persona de test"))
    school = School(id="onboarding-school", name="École", short_name="ON", color="#000000")
    db_session.add(school)
    db_session.flush()
    db_session.add(Skill(id="onboarding-skill", school_id=school.id, name="Compétence de test"))
    db_session.add(Goal(id="test-goal", label="Objectif de test"))
    db_session.commit()


def test_profile_starts_empty_before_any_onboarding(client):
    headers = _register_and_login(client)
    resp = client.get("/api/me/onboarding-profile", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["onboarding_done"] is False
    assert body["profile_type_id"] is None
    assert body["goal_ids"] == []


def test_onboarding_profile_requires_authentication(client):
    resp = client.get("/api/me/onboarding-profile")
    assert resp.status_code == 401  # pas de header Authorization du tout


def test_put_creates_the_profile_and_syncs_goals_and_skills(client, db_session):
    _seed_catalog(db_session)
    headers = _register_and_login(client, "onboarding-put@example.com")

    resp = client.put(
        "/api/me/onboarding-profile",
        headers=headers,
        json={
            "profile_type_id": "test-persona",
            "level": "Intermédiaire",
            "career_objectives": "Devenir data engineer",
            "goal_ids": ["test-goal"],
            "interest_skill_ids": ["onboarding-skill"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["onboarding_done"] is True
    assert body["profile_type_id"] == "test-persona"
    assert body["goal_ids"] == ["test-goal"]
    assert body["interest_skill_ids"] == ["onboarding-skill"]

    # Persisté : une lecture séparée retrouve les mêmes valeurs.
    reread = client.get("/api/me/onboarding-profile", headers=headers)
    assert reread.json() == body


def test_put_replaces_goals_and_skills_rather_than_accumulating(client, db_session):
    db_session.add_all([Goal(id="goal-a", label="A"), Goal(id="goal-b", label="B")])
    db_session.commit()
    headers = _register_and_login(client, "onboarding-replace@example.com")

    client.put(
        "/api/me/onboarding-profile", headers=headers,
        json={"profile_type_id": None, "level": None, "career_objectives": None,
              "goal_ids": ["goal-a", "goal-b"], "interest_skill_ids": []},
    )
    second = client.put(
        "/api/me/onboarding-profile", headers=headers,
        json={"profile_type_id": None, "level": None, "career_objectives": None,
              "goal_ids": ["goal-b"], "interest_skill_ids": []},
    )

    assert second.json()["goal_ids"] == ["goal-b"]


def test_profile_types_and_goals_catalogs_are_public(client, db_session):
    _seed_catalog(db_session)
    # Aucun header Authorization — ce sont des catalogues publics, comme
    # /api/schools et /api/skills.
    types_resp = client.get("/api/profile-types")
    goals_resp = client.get("/api/goals")
    assert types_resp.status_code == 200
    assert goals_resp.status_code == 200
    assert any(t["id"] == "test-persona" for t in types_resp.json())
    assert any(g["id"] == "test-goal" for g in goals_resp.json())
