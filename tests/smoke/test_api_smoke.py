"""
Smoke tests pós-deploy — validam que a API está viva e respondendo corretamente.

Executado pelo CI/CD após subir o ambiente de staging, antes de promover para produção.
Todas as fixtures (base_url, api_key, auth_headers) são definidas em conftest.py.

Uso local:
    export API_BASE_URL=http://localhost:8100
    export API_KEY=staging-test-key
    pytest tests/smoke/ -v

Grupos de testes:
    TestHealth           — liveness + readiness
    TestAuthentication   — gate de segurança (sem key → 401)
    TestSecurityHeaders  — cabeçalhos HTTP de segurança
    TestMetrics          — endpoint /metrics (UCM-22: Prometheus)
    TestCarsEndpoint     — listagem e campos obrigatórios
    TestPricePrediction  — predição de preço ML
    TestResponseSLA      — SLA de tempo de resposta (< 2s p95)
"""
from __future__ import annotations

import time

import pytest
import requests


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_endpoint_returns_200(self, base_url: str, smoke_timeout: int):
        """GET /health deve retornar 200 sem autenticação."""
        r = requests.get(f"{base_url}/health", timeout=smoke_timeout)
        assert r.status_code == 200, f"Esperado 200, obtido {r.status_code}: {r.text}"

    def test_health_response_has_status_field(self, base_url: str, smoke_timeout: int):
        r = requests.get(f"{base_url}/health", timeout=smoke_timeout)
        body = r.json()
        assert "status" in body, f"Campo 'status' ausente: {body}"
        assert body["status"] in ("ok", "healthy", "UP"), (
            f"Status inesperado: {body['status']}"
        )

    def test_health_response_has_version(self, base_url: str, smoke_timeout: int):
        r = requests.get(f"{base_url}/health", timeout=smoke_timeout)
        body = r.json()
        assert "version" in body, f"Campo 'version' ausente: {body}"

    def test_health_returns_json(self, base_url: str, smoke_timeout: int):
        r = requests.get(f"{base_url}/health", timeout=smoke_timeout)
        assert "application/json" in r.headers.get("content-type", ""), (
            f"Content-Type inesperado: {r.headers.get('content-type')}"
        )


# ── Autenticação ──────────────────────────────────────────────────────────────

class TestAuthentication:
    def test_cars_without_api_key_returns_401(self, base_url: str, smoke_timeout: int):
        """Endpoints protegidos sem X-API-Key → 401."""
        r = requests.get(f"{base_url}/api/v1/cars", timeout=smoke_timeout)
        assert r.status_code == 401, (
            f"Esperado 401, obtido {r.status_code} — API key não está sendo validada"
        )

    def test_cars_with_wrong_api_key_returns_401(self, base_url: str, smoke_timeout: int):
        """X-API-Key incorreta → 401."""
        r = requests.get(
            f"{base_url}/api/v1/cars",
            headers={"X-API-Key": "wrong-key-that-does-not-exist"},
            timeout=smoke_timeout,
        )
        assert r.status_code == 401, f"Esperado 401, obtido {r.status_code}"

    def test_analytics_without_key_returns_401(self, base_url: str, smoke_timeout: int):
        """Endpoint analytics também deve exigir autenticação."""
        r = requests.get(f"{base_url}/api/v1/analytics/summary", timeout=smoke_timeout)
        assert r.status_code in (401, 404), (
            f"Esperado 401 (ou 404 se rota não existe), obtido {r.status_code}"
        )

    def test_authenticated_request_succeeds(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        """Com API_KEY correta deve retornar 200."""
        r = requests.get(
            f"{base_url}/api/v1/cars",
            headers=auth_headers,
            params={"limit": 1},
            timeout=smoke_timeout,
        )
        assert r.status_code == 200, (
            f"Esperado 200 com API_KEY válida, obtido {r.status_code}: {r.text}"
        )


# ── Security Headers ──────────────────────────────────────────────────────────

class TestSecurityHeaders:
    """
    Valida presença dos headers HTTP de segurança configurados em main.py (M-03).

    Estes headers protegem contra XSS, clickjacking e sniffing de content-type.
    """

    def _get_response(self, base_url: str, timeout: int) -> requests.Response:
        return requests.get(f"{base_url}/health", timeout=timeout)

    def test_x_content_type_options(self, base_url: str, smoke_timeout: int):
        r = self._get_response(base_url, smoke_timeout)
        assert r.headers.get("X-Content-Type-Options") == "nosniff", (
            f"X-Content-Type-Options ausente ou incorreto: {r.headers.get('X-Content-Type-Options')}"
        )

    def test_x_frame_options(self, base_url: str, smoke_timeout: int):
        r = self._get_response(base_url, smoke_timeout)
        assert r.headers.get("X-Frame-Options") == "DENY", (
            f"X-Frame-Options ausente ou incorreto: {r.headers.get('X-Frame-Options')}"
        )

    def test_x_xss_protection(self, base_url: str, smoke_timeout: int):
        r = self._get_response(base_url, smoke_timeout)
        xss = r.headers.get("X-XSS-Protection", "")
        assert "1" in xss, f"X-XSS-Protection ausente ou incorreto: {xss}"

    def test_referrer_policy(self, base_url: str, smoke_timeout: int):
        r = self._get_response(base_url, smoke_timeout)
        referrer = r.headers.get("Referrer-Policy", "")
        assert referrer, f"Referrer-Policy ausente"

    def test_cache_control_no_store(self, base_url: str, smoke_timeout: int):
        r = self._get_response(base_url, smoke_timeout)
        cc = r.headers.get("Cache-Control", "")
        assert "no-store" in cc, f"Cache-Control não contém 'no-store': {cc}"

    def test_correlation_id_returned(self, base_url: str, smoke_timeout: int):
        """API deve retornar X-Correlation-ID em toda resposta."""
        custom_id = "smoke-test-correlation-123"
        r = requests.get(
            f"{base_url}/health",
            headers={"X-Correlation-ID": custom_id},
            timeout=smoke_timeout,
        )
        assert r.headers.get("X-Correlation-ID") == custom_id, (
            f"X-Correlation-ID não ecoado: {r.headers.get('X-Correlation-ID')}"
        )


# ── Metrics (UCM-22: Prometheus) ──────────────────────────────────────────────

class TestMetrics:
    """
    Valida o endpoint /metrics exposto pelo prometheus-fastapi-instrumentator (UCM-22).

    /metrics é público (sem autenticação) para permitir scraping pelo Prometheus.
    """

    def test_metrics_endpoint_returns_200(self, base_url: str, smoke_timeout: int):
        """GET /metrics deve retornar 200 sem autenticação."""
        r = requests.get(f"{base_url}/metrics", timeout=smoke_timeout)
        assert r.status_code == 200, (
            f"Esperado 200, obtido {r.status_code} — /metrics não disponível "
            "(prometheus-fastapi-instrumentator pode não estar instalado)"
        )

    def test_metrics_content_type_is_prometheus(self, base_url: str, smoke_timeout: int):
        """Content-Type deve ser text/plain (formato Prometheus exposition)."""
        r = requests.get(f"{base_url}/metrics", timeout=smoke_timeout)
        if r.status_code != 200:
            pytest.skip("/metrics não disponível")
        ct = r.headers.get("content-type", "")
        assert "text/plain" in ct, f"Content-Type inesperado para /metrics: {ct}"

    def test_metrics_contains_http_requests_total(self, base_url: str, smoke_timeout: int):
        """Deve conter métrica padrão http_requests_total."""
        r = requests.get(f"{base_url}/metrics", timeout=smoke_timeout)
        if r.status_code != 200:
            pytest.skip("/metrics não disponível")
        # Fazer uma requisição primeiro para garantir que a métrica existe
        requests.get(f"{base_url}/health", timeout=smoke_timeout)
        r2 = requests.get(f"{base_url}/metrics", timeout=smoke_timeout)
        assert "http_requests_total" in r2.text, (
            "Métrica http_requests_total não encontrada em /metrics"
        )

    def test_metrics_contains_custom_prediction_metric(self, base_url: str, smoke_timeout: int):
        """Deve conter métrica customizada api_predictions_total (UCM-22)."""
        r = requests.get(f"{base_url}/metrics", timeout=smoke_timeout)
        if r.status_code != 200:
            pytest.skip("/metrics não disponível")
        assert "api_predictions" in r.text, (
            "Métrica api_predictions não encontrada — "
            "verifique se telemetry._init_metrics() foi chamado na inicialização"
        )


# ── Cars Endpoint ─────────────────────────────────────────────────────────────

class TestCarsEndpoint:
    def test_cars_list_returns_200(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        """GET /api/v1/cars com autenticação deve retornar 200."""
        r = requests.get(
            f"{base_url}/api/v1/cars",
            headers=auth_headers,
            params={"limit": 5},
            timeout=smoke_timeout,
        )
        assert r.status_code == 200, f"Status {r.status_code}: {r.text}"

    def test_cars_list_returns_list(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        r = requests.get(
            f"{base_url}/api/v1/cars",
            headers=auth_headers,
            params={"limit": 5},
            timeout=smoke_timeout,
        )
        body = r.json()
        assert isinstance(body, list), f"Esperado list, obtido {type(body)}: {body}"

    def test_cars_list_items_have_required_fields(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        r = requests.get(
            f"{base_url}/api/v1/cars",
            headers=auth_headers,
            params={"limit": 1},
            timeout=smoke_timeout,
        )
        items = r.json()
        if not items:
            pytest.skip("Nenhum carro no banco — banco vazio em staging")
        car = items[0]
        for field in ("id", "price", "year", "manufacturer"):
            assert field in car, f"Campo '{field}' ausente no item: {car}"

    def test_cars_limit_param_is_respected(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        """Parâmetro limit deve limitar a quantidade retornada."""
        r = requests.get(
            f"{base_url}/api/v1/cars",
            headers=auth_headers,
            params={"limit": 3},
            timeout=smoke_timeout,
        )
        items = r.json()
        assert len(items) <= 3, f"limit=3 retornou {len(items)} itens"

    def test_cars_invalid_limit_returns_4xx(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        """Limit negativo deve retornar erro de validação (422)."""
        r = requests.get(
            f"{base_url}/api/v1/cars",
            headers=auth_headers,
            params={"limit": -1},
            timeout=smoke_timeout,
        )
        assert r.status_code in (400, 422), (
            f"Esperado 400/422 para limit negativo, obtido {r.status_code}"
        )


# ── Price Prediction ──────────────────────────────────────────────────────────

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

    def test_predict_returns_expected_status(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        """POST /api/v1/cars/predict deve retornar 200 ou 503 (modelo não treinado)."""
        r = requests.post(
            f"{base_url}/api/v1/cars/predict",
            headers=auth_headers,
            json=self.SAMPLE_PAYLOAD,
            timeout=smoke_timeout,
        )
        assert r.status_code in (200, 503), (
            f"Status inesperado {r.status_code}: {r.text}"
        )

    def test_predict_returns_numeric_price(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        """Predição deve retornar um preço numérico positivo."""
        r = requests.post(
            f"{base_url}/api/v1/cars/predict",
            headers=auth_headers,
            json=self.SAMPLE_PAYLOAD,
            timeout=smoke_timeout,
        )
        if r.status_code == 503:
            pytest.skip("Modelo não disponível no staging — treine primeiro")
        body = r.json()
        price = body.get("predicted_price") or body.get("price") or body.get("prediction")
        assert price is not None, f"Campo de preço não encontrado: {body}"
        assert isinstance(price, (int, float)), f"Preço não é numérico: {price}"
        assert price > 0, f"Preço deve ser positivo, obtido: {price}"

    def test_predict_without_required_field_returns_422(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        """Payload incompleto deve retornar 422 (Unprocessable Entity)."""
        incomplete = {"year": 2020}  # faltam campos obrigatórios
        r = requests.post(
            f"{base_url}/api/v1/cars/predict",
            headers=auth_headers,
            json=incomplete,
            timeout=smoke_timeout,
        )
        assert r.status_code in (400, 422, 503), (
            f"Esperado 422 para payload inválido, obtido {r.status_code}"
        )


# ── OpenAPI / Docs ────────────────────────────────────────────────────────────

class TestOpenAPI:
    def test_openapi_docs_accessible_in_staging(self, base_url: str, smoke_timeout: int):
        """
        Em staging (não produção) o Swagger UI deve estar acessível para debugging.
        Em produção, docs_url=None bloqueia o acesso.
        """
        r = requests.get(f"{base_url}/docs", timeout=smoke_timeout)
        # 200 em staging/dev; 404 em produção (docs_url=None)
        assert r.status_code in (200, 404), (
            f"Status inesperado para /docs: {r.status_code}"
        )

    def test_openapi_schema_has_paths(self, base_url: str, smoke_timeout: int):
        r = requests.get(f"{base_url}/openapi.json", timeout=smoke_timeout)
        if r.status_code == 404:
            pytest.skip("OpenAPI desabilitado neste ambiente (produção)")
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        assert len(schema["paths"]) > 0, "OpenAPI schema sem paths registrados"


# ── SLA de tempo de resposta ──────────────────────────────────────────────────

class TestResponseSLA:
    """
    Valida SLA de tempo de resposta para os endpoints críticos.

    SLA target:
      /health           < 200ms (liveness — deve ser imediato)
      /api/v1/cars      < 2000ms (com DB query)
      /metrics          < 500ms (scraping rápido)
    """

    SLA_HEALTH_MS  = 200
    SLA_CARS_MS    = 2000
    SLA_METRICS_MS = 500

    def test_health_response_time(self, base_url: str, smoke_timeout: int):
        """Health check deve responder em menos de 200ms."""
        start = time.monotonic()
        r = requests.get(f"{base_url}/health", timeout=smoke_timeout)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert r.status_code == 200
        assert elapsed_ms < self.SLA_HEALTH_MS, (
            f"/health demorou {elapsed_ms:.0f}ms — SLA é {self.SLA_HEALTH_MS}ms"
        )

    def test_cars_list_response_time(
        self, base_url: str, auth_headers: dict[str, str], smoke_timeout: int
    ):
        """Listagem de carros deve responder em menos de 2s."""
        start = time.monotonic()
        r = requests.get(
            f"{base_url}/api/v1/cars",
            headers=auth_headers,
            params={"limit": 10},
            timeout=smoke_timeout,
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        assert r.status_code == 200
        assert elapsed_ms < self.SLA_CARS_MS, (
            f"/api/v1/cars demorou {elapsed_ms:.0f}ms — SLA é {self.SLA_CARS_MS}ms"
        )

    def test_metrics_response_time(self, base_url: str, smoke_timeout: int):
        """Endpoint /metrics deve responder em menos de 500ms."""
        r = requests.get(f"{base_url}/metrics", timeout=smoke_timeout)
        if r.status_code != 200:
            pytest.skip("/metrics não disponível")
        start = time.monotonic()
        r2 = requests.get(f"{base_url}/metrics", timeout=smoke_timeout)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert r2.status_code == 200
        assert elapsed_ms < self.SLA_METRICS_MS, (
            f"/metrics demorou {elapsed_ms:.0f}ms — SLA é {self.SLA_METRICS_MS}ms"
        )
