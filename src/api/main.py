from __future__ import annotations

import logging
import os
import secrets
import sys
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.api_key import APIKeyHeader

load_dotenv()

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ── ambiente e segurança ──────────────────────────────────────────────────────
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
_IS_PROD_LIKE = _ENVIRONMENT in ("production", "staging")
_API_KEY = os.getenv("API_KEY", "")

# C-03 FIX: fail-closed — em produção/staging sem API_KEY, o processo para.
if _IS_PROD_LIKE and not _API_KEY:
    logger.critical(
        "API_KEY não definida em ambiente '%s'. "
        "Defina API_KEY no .env ou nas variáveis de ambiente. Encerrando.",
        _ENVIRONMENT,
    )
    sys.exit(1)

if not _API_KEY:
    logger.warning(
        "API_KEY não configurada — autenticação desativada (modo desenvolvimento). "
        "Defina API_KEY antes de usar em staging/produção."
    )

# ── app — docs desabilitados em produção (M-01) ───────────────────────────────
_docs_url    = None if _IS_PROD_LIKE else "/docs"
_redoc_url   = None if _IS_PROD_LIKE else "/redoc"
_openapi_url = None if _IS_PROD_LIKE else "/openapi.json"

app = FastAPI(
    title="Used Cars Market Analysis API",
    description=(
        "API for analyzing used car listings data with focus on financing options.\n\n"
        "**Authentication**: all endpoints (except `/health`) require the header "
        "`X-API-Key: <your_key>` configured in the `API_KEY` environment variable."
    ),
    version="1.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

# ── CORS — allow_credentials=False pois usamos header X-API-Key (M-05) ────────
_raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:8501")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type", "Accept"],
)

# ── API Key authentication ────────────────────────────────────────────────────
_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str | None = Security(_API_KEY_HEADER)) -> str:
    """
    Dependência reutilizável nos routers.
    Retorna a key se válida; lança 401 caso contrário.
    /health é público — não usa esta dependência.
    """
    if not _API_KEY:
        return "dev-no-auth"

    # M-06 FIX: comparação constant-time para evitar timing attack
    if not secrets.compare_digest(api_key or "", _API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou ausente. Forneça o header X-API-Key.",
        )
    return api_key


# ── endpoints públicos ────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Endpoint público de health check — sem autenticação."""
    # M-04 FIX: não vazar informações de configuração interna
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


# ── error handlers ────────────────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.error("HTTP %s — %s  [%s %s]", exc.status_code, exc.detail,
                 request.method, request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro não tratado em %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500},
    )


# ── routers ───────────────────────────────────────────────────────────────────
from .routers import analytics, cars, financing  # noqa: E402

app.include_router(
    cars.router,
    prefix="/api/v1/cars",
    tags=["cars"],
    dependencies=[Security(require_api_key)],
)
app.include_router(
    financing.router,
    prefix="/api/v1/financing",
    tags=["financing"],
    dependencies=[Security(require_api_key)],
)
app.include_router(
    analytics.router,
    prefix="/api/v1/analytics",
    tags=["analytics"],
    dependencies=[Security(require_api_key)],
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", 8000)),
        reload=os.getenv("API_RELOAD", "true").lower() == "true",
    )
