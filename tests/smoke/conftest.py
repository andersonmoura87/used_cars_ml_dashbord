"""
Fixtures compartilhadas para smoke tests pós-deploy.

O conftest resolve dois problemas do arquivo original:
  1. O RuntimeError em módulo-load bloqueava pytest --collect-only
  2. Fixtures de sessão compartilhadas evitam repetição de lógica de wait/retry
"""
from __future__ import annotations

import os
import time

import pytest
import requests


# ── Configuração ──────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Registra marks customizados para evitar avisos do pytest."""
    config.addinivalue_line("markers", "smoke: smoke tests pós-deploy (requerem API viva)")
    config.addinivalue_line("markers", "sla: testes de SLA (tempo de resposta)")


# ── Fixtures de sessão ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def base_url() -> str:
    """URL base da API em staging. Configurável via API_BASE_URL."""
    return os.getenv("API_BASE_URL", "http://localhost:8100").rstrip("/")


@pytest.fixture(scope="session")
def api_key() -> str:
    """
    Chave de API para smoke tests.

    Se API_KEY não estiver definida, todos os testes que dependem desta
    fixture são pulados (ao invés de falhar com RuntimeError).
    """
    key = os.getenv("API_KEY", "")
    if not key:
        pytest.skip(
            "API_KEY não definida — exporte API_KEY=<chave> para rodar smoke tests. "
            "No CI: configure o secret STAGING_API_KEY."
        )
    return key


@pytest.fixture(scope="session")
def auth_headers(api_key: str) -> dict[str, str]:
    """Headers de autenticação prontos para uso."""
    return {"X-API-Key": api_key}


@pytest.fixture(scope="session")
def smoke_timeout() -> int:
    """Timeout em segundos por requisição (configurável via SMOKE_TIMEOUT)."""
    return int(os.getenv("SMOKE_TIMEOUT", "15"))


@pytest.fixture(scope="session", autouse=True)
def wait_for_api(base_url: str) -> None:
    """
    Aguarda a API ficar disponível antes de qualquer teste (max 90s).

    Se a API não responder, pula toda a sessão de smoke tests ao invés
    de falhar — isso evita que 'pytest tests/' no CI quebre por incluir
    tests/smoke/ sem uma API rodando.

    Para forçar falha (ex: em pipeline de staging onde a API DEVE estar
    disponível), defina a variável: SMOKE_STRICT=true
    """
    url = f"{base_url}/health"
    max_wait = int(os.getenv("SMOKE_WAIT_SECONDS", "90"))
    strict_mode = os.getenv("SMOKE_STRICT", "false").lower() == "true"
    deadline = time.time() + max_wait
    attempt = 0

    while time.time() < deadline:
        attempt += 1
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                print(f"\nAPI disponível após {attempt} tentativas em {url}")
                return
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
            pass
        time.sleep(3)

    msg = (
        f"API não respondeu em {url} após {max_wait}s ({attempt} tentativas). "
        "Verifique os logs: docker compose -f docker-compose.staging.yml logs app"
    )
    if strict_mode:
        pytest.fail(msg)
    else:
        pytest.skip(f"API indisponível — smoke tests pulados. {msg}")
