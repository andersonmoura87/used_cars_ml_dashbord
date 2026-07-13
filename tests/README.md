# Testes

## Estrutura

```
tests/
├── unit/               # Testes unitários (sem I/O, sem serviços externos)
│   ├── test_cleaning.py
│   └── test_db.py
├── integration/        # Testes de integração (requerem DB ou serviços)
│   └── (futuro)
├── smoke/              # Smoke tests pós-deploy (requerem API rodando)
│   └── test_api_smoke.py
├── test_pipeline.py            # Pipeline ETL (alguns skipped em CI)
├── test_ge_validation.py       # Great Expectations (mock-based)
└── test_mlflow_integration.py  # MLflow tracking (mock-based)
```

## Executar

```bash
# Todos os testes (exceto smoke)
pytest

# Apenas unitários
pytest tests/unit/

# Integração (requer DB e Redis rodando)
pytest tests/integration/

# Smoke (requer API em http://localhost:8000)
pytest tests/smoke/
```

## Marcadores

- `@pytest.mark.skip` — desabilitado temporariamente (registrar issue Jira)
- `@pytest.mark.slow` — testes lentos (excluir com `-m "not slow"`)
