"""
Configuration centralisée de l'application, lue depuis les variables
d'environnement (cf. §25 cahier des charges technique — aucun secret en dur
dans le code). En développement, un fichier `.env` local peut fournir ces
variables ; il ne doit jamais être versionné (voir .env.example).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Application ---------------------------------------------------
    app_name: str = "CASA AI Institute API"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    frontend_url: str = Field(
        default="http://localhost:5173",
        description="Base du frontend, utilisée pour construire les liens envoyés par email (ex: réinitialisation de mot de passe).",
    )

    # --- Base de données -------------------------------------------------
    # Format attendu : postgresql+psycopg2://user:password@host:port/dbname
    database_url: str = Field(
        default="postgresql+psycopg2://casa:casa@localhost:5432/casa_dev",
        description="URL de connexion PostgreSQL (variable DATABASE_URL).",
    )
    db_echo: bool = False               # log SQL (à activer en debug uniquement)
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # --- Sécurité / auth (utilisé à l'étape Authentification) ---------------
    secret_key: str = Field(
        default="changeme-in-env-never-commit-a-real-secret",
        description="Clé de signature JWT (variable SECRET_KEY).",
    )
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- Redis (cache / tâches asynchrones, §11 CDC technique) --------------
    redis_url: str = "redis://localhost:6379/0"

    # --- Stockage objet (§10 CDC technique — MinIO en local) -----------------
    storage_endpoint: str = "http://localhost:9000"
    storage_bucket: str = "casa-resources"

    # --- Médias (images de sections de leçon) --------------------------------
    # MVP : disque local servi en statique par FastAPI. Le backend S3/MinIO
    # (storage_endpoint/storage_bucket ci-dessus) est déjà anticipé dans le
    # cahier technique mais pas encore câblé ; StorageService (services/
    # storage_service.py) isole ce choix pour permettre de basculer vers
    # MinIO/S3 sans toucher aux routes ni au modèle de données.
    media_root: str = "media"                 # dossier local (relatif au CWD du process backend)
    media_public_base_url: str = "/media"      # préfixe servi par app.mount(StaticFiles)
    media_max_upload_mb: int = 5
    media_allowed_content_types: tuple[str, ...] = (
        "image/jpeg", "image/png", "image/webp", "image/gif",
    )

    # --- IA (préparé pour V5/V6, sans impact avant) --------------------------
    ai_model_url: str | None = None

    # --- CORS -----------------------------------------------------------
    # En développement, seule l'origine locale du frontend Vite est autorisée.
    # En production, il n'y a intentionnellement AUCUNE valeur par défaut :
    # sans CORS_ALLOWED_ORIGINS renseignée, l'API refuse toute requête
    # cross-origin plutôt que d'ouvrir silencieusement l'accès à un domaine
    # non prévu. Format : une ou plusieurs origines séparées par des virgules
    # (ex: "https://app.casa-ai.fr,https://casa-ai.fr").
    cors_allowed_origins: str = Field(
        default="",
        description="Origines autorisées en production, séparées par des virgules (CORS_ALLOWED_ORIGINS).",
    )

    @property
    def cors_origins(self) -> list[str]:
        if not self.is_production:
            return ["http://localhost:5173"]
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        # Validation légère : on s'assure que l'URL est bien au format Postgres
        # attendu par SQLAlchemy + psycopg2, sans forcer un parsing strict qui
        # rejetterait des variantes valides (ex: +psycopg vs +psycopg2).
        if not v.startswith(("postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://")):
            raise ValueError(
                "database_url doit commencer par postgresql:// ou postgresql+psycopg2://"
            )
        return v

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Instance unique (mise en cache) des paramètres, à injecter via
    Depends(get_settings) dans les routes FastAPI si besoin."""
    return Settings()


settings = get_settings()
