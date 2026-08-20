"""Tests d'intégration sur /api/auth/* — inscription, connexion, mot de
passe oublié/réinitialisation, changement de mot de passe."""
from __future__ import annotations

from app.core.security import create_reset_password_token
from app.repositories.user_repository import UserRepository


def _register(client, email: str, password: str = "SuperSecret123!"):
    return client.post(
        "/api/auth/register",
        json={"first_name": "Ada", "last_name": "Lovelace", "email": email, "password": password},
    )


def test_register_creates_a_learner(client):
    resp = _register(client, "ada@example.com")
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "LEARNER"
    assert body["email"] == "ada@example.com"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_rejects_duplicate_email(client):
    assert _register(client, "dup@example.com").status_code == 201
    assert _register(client, "dup@example.com").status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"first_name": "Ada", "last_name": "Lovelace", "email": "short@example.com", "password": "short"},
    )
    assert resp.status_code == 422


def test_login_succeeds_with_correct_credentials(client):
    _register(client, "login-ok@example.com")
    resp = client.post("/api/auth/login", json={"email": "login-ok@example.com", "password": "SuperSecret123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_rejects_wrong_password(client):
    _register(client, "login-bad@example.com")
    resp = client.post("/api/auth/login", json={"email": "login-bad@example.com", "password": "WrongPassword!"})
    assert resp.status_code == 401


def test_login_error_message_does_not_reveal_which_field_is_wrong(client):
    _register(client, "enum@example.com")
    wrong_password = client.post("/api/auth/login", json={"email": "enum@example.com", "password": "WrongPassword!"})
    unknown_email = client.post("/api/auth/login", json={"email": "nobody-enum@example.com", "password": "WrongPassword!"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_forgot_password_returns_204_whether_or_not_the_email_exists(client):
    _register(client, "fp-known@example.com")
    known = client.post("/api/auth/forgot-password", json={"email": "fp-known@example.com"})
    unknown = client.post("/api/auth/forgot-password", json={"email": "fp-unknown@example.com"})
    assert known.status_code == 204
    assert unknown.status_code == 204


def test_reset_password_with_valid_token_changes_the_password(client, db_session):
    _register(client, "reset@example.com", password="OldPassword123!")
    user = UserRepository(db_session).get_by_email("reset@example.com")
    token = create_reset_password_token(user.id)

    resp = client.post("/api/auth/reset-password", json={"token": token, "new_password": "NewPassword456!"})
    assert resp.status_code == 204

    old_login = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "OldPassword123!"})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "NewPassword456!"})
    assert new_login.status_code == 200


def test_reset_password_rejects_an_invalid_token(client):
    resp = client.post("/api/auth/reset-password", json={"token": "not-a-real-token", "new_password": "NewPassword456!"})
    assert resp.status_code == 400


def test_reset_password_rejects_an_access_token_used_as_a_reset_token(client):
    """Un access token valide ne doit pas pouvoir servir de token de
    réinitialisation — decode_token doit rejeter un type de token inattendu
    (cf. app/core/security.py)."""
    _register(client, "typecheck@example.com")
    login = client.post("/api/auth/login", json={"email": "typecheck@example.com", "password": "SuperSecret123!"})
    access_token = login.json()["access_token"]

    resp = client.post("/api/auth/reset-password", json={"token": access_token, "new_password": "NewPassword456!"})
    assert resp.status_code == 400


def test_change_password_requires_the_correct_current_password(client):
    _register(client, "chpw@example.com", password="OldPassword123!")
    login = client.post("/api/auth/login", json={"email": "chpw@example.com", "password": "OldPassword123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    wrong = client.post(
        "/api/auth/me/password",
        json={"current_password": "WrongOld!", "new_password": "Whatever123!"},
        headers=headers,
    )
    assert wrong.status_code == 401

    correct = client.post(
        "/api/auth/me/password",
        json={"current_password": "OldPassword123!", "new_password": "NewPass789!"},
        headers=headers,
    )
    assert correct.status_code == 204

    relogin = client.post("/api/auth/login", json={"email": "chpw@example.com", "password": "NewPass789!"})
    assert relogin.status_code == 200
