from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin_certifications import router as admin_certifications_router
from app.api.admin_content import router as admin_content_router
from app.api.admin_media import router as admin_media_router
from app.api.admin_progress import router as admin_progress_router
from app.api.admin_quiz import router as admin_quiz_router
from app.api.admin_users import router as admin_users_router
from app.api.auth import router as auth_router
from app.api.certifications import router as certifications_router
from app.api.content import router as content_router
from app.api.portfolio import router as portfolio_router
from app.api.progress import router as progress_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

# En développement, le frontend Vite tourne sur un port différent. En
# production, les origines viennent de CORS_ALLOWED_ORIGINS (voir Settings)
# — jamais de valeur par défaut qui ouvrirait ou fermerait silencieusement
# l'accès sans que ce soit un choix explicite au déploiement.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(content_router)
app.include_router(progress_router)
app.include_router(portfolio_router)
app.include_router(certifications_router)
app.include_router(admin_users_router)
app.include_router(admin_content_router)
app.include_router(admin_media_router)
app.include_router(admin_progress_router)
app.include_router(admin_quiz_router)
app.include_router(admin_certifications_router)

# Sert les images uploadées (sections de leçon, cf. services/storage_service.py
# et api/admin_media.py). Le dossier est créé s'il n'existe pas encore — sinon
# StaticFiles refuse de démarrer sur un chemin absent.
_media_root = Path(settings.media_root)
_media_root.mkdir(parents=True, exist_ok=True)
app.mount(settings.media_public_base_url, StaticFiles(directory=_media_root), name="media")


@app.get("/api/health", tags=["health"])
def health() -> dict:
    return {"status": "ok", "environment": settings.environment}
