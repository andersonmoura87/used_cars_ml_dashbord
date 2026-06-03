"""
Smoke tests pós-deploy — validam que a API está viva e respondendo corretamente.

Executado pelo CI/CD após subir o ambiente de staging, antes de promover para produção.

Uso local:
    API_BASE_URL=http://localhost:8100 API_KEY=staging-test-key pytest tests/smoke/ -v

Variáveis de ambiente:
    API_BASE_URL   — URL base da API (default: http://localhost:8100)
    API_KEY        — chave de autenticação (default: staging-test-key)
    SMOKE_TIMEOUT  — timeout em segundos por request (default: 10)
"""
from __future__ import annotations

import os
import time

import pytest
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8100").rstrip("/")
API_KEY      = os.getenv("API_KEY", "staging-test-key")
TIMEOUT      = int(os.getenv("SMOKE_TIMEOUT", "10"))

AUTH_HEADERS = {"X-API-Key": API_KEY}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def wait_for_api():
    """Aguarda a API ficar disponível antes de rodar os testes (max 60s)."""
    url = f"{API_BASE_URL}/health"
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=3)
            if r.status_code == 200:
                return
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(2)
    pytest.fail(f"API não respondeu em {url} após 60 segundos.")


# ── Testes ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_endpoint_returns_200(self):
        """GET /health deve retornar 200 sem autenticação."""
        r = requests.get(f"{API_BASE_URL}/health", timeout=TIMEOUT)
        assert r.status_code == 200, f"Esperado 200, obtido {r.status_code}: {r.text}"

    def test_health_response_has_status_ok(self):
        r = requests.get(f"{API_BASE_URL}/health", timeout=TIMEOUT)
        body = r.json()
        assert body.get("status") in ("ok", "healthy", "UP"), (
            f"Campo 'status' inesperado: {body}"
        )


class TestAuthentication:
    def test_cars_without_api_key_returns_401(self):
        """Endpoints protegidos devem retornar 401 sem X-API-Key."""
        r = requests.get(f"{API_BASE_URL}/api/v1/cars", timeout=TIMEOUT)
        assert r.status_code == 401, (
            f"Esperado 401, obtido {r.status_code} — API key não está sendo validada"
        )

    def test_cars_with_wrong_api_key_returns_401(self):
        r = requests.get(
            f"{API_BASE_URL}/api/v1/cars",
            headers={"X-API-Key": "wrong-key"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401


class TestCarsEndpoint:
    def test_cars_list_returns_200(self):
        """GET /api/v1/cars com autenticação deve retornar 200."""
        r = requests.get(
            f"{API_BASE_URL}/api/v1/cars",
            headers=AUTH_HEADERS,
            params={"limit": 5},
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"

    def test_cars_list_returns_list(self):
        r = requests.get(
            f"{API_BASE_URL}/api/v1/cars",
            headers=AUTH_HEADERS,
            params={"limit": 5},
            timeout=TIMEOUT,
        )
        body = r.json()
        assert isinstance(body, list), f"Esperado list, obtido {type(body)}: {body}"

    def test_cars_list_items_have_required_fields(self):
        r = requests.get(
            f"{API_BASE_URL}/api/v1/cars",
            headers=AUTH_HEADERS,
            params={"limit": 1},
            timeout=TIMEOUT,
        )
        items = r.json()
        if not items:
            pytest.skip("Nenhum carro no banco — pule este teste em ambiente vazio")
        car = items[0]
        for field in ("id", "price", "year", "manufacturer"):
            assert field in car, f"Campo '{field}' ausente no item: {car}"


class TestPricePrediction:
    SAMPLE_PAYLOAD = {
        "year": 2019,
        "manufacturer": "toyota",
        "model": "camry",
        "condition": "good",
        "fuel": "gas",
        "odometer": 45000,
        "transmission": "automatic",
        "drive": "fwd",
        "type": "sedan",
        "paint_color": "white",
        "state": "ca",
    }

    def test_predict_returns_200(self):
        """POST /api/v1/cars/predict deve retornar 200 com payload válido."""
        r = requests.post(
            f"{API_BASE_URL}/api/v1/cars/predict",
            headers=AUTH_HEADERS,
            json=self.SAMPLE_PAYLOAD,
            timeout=TIMEOUT,
        )
        # 200 se modelo carregado; 503 se modelo ainda não treinado
        assert r.status_code in (200, 503), (
            f"Status inesperado {r.status_code}: {r.text}"
        )

    def test_predict_returns_numeric_price(self):
        """Predição deve retornar um preço numérico positivo."""
        r = requests.post(
            f"{API_BASE_URL}/api/v1/cars/predict",
            headers=AUTH_HEADERS,
            json=self.SAMPLE_PAYLOAD,
            timeout=TIMEOUT,
        )
        if r.status_code == 503:
            pytest.skip("Modelo não disponível no staging — treine primeiro")
        body = r.json()
        price = body.get("predicted_price") or body.get("price") or body.get("prediction")
        assert price is not None, f"Campo de preço não encontrado: {body}"
        assert isinstance(price, (int, float)), f"Preço não é numérico: {price}"
        assert price > 0, f"Preço deve ser positivo, obtido: {price}"


class TestOpenAPI:
    def test_openapi_docs_accessible(self):
        """Swagger UI deve estar acessível."""
        r = requests.get(f"{API_BASE_URL}/docs", timeout=TIMEOUT)
        assert r.status_code == 200

    def test_openapi_schema_has_paths(self):
        r = requests.get(f"{API_BASE_URL}/openapi.json", timeout=TIMEOUT)
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        assert len(schema["paths"]) > 0, "OpenAPI schema sem paths registrados"
