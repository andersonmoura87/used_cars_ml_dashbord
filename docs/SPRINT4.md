# Sprint 4 — Backlog (UCM-27+)

**Objetivo:** fechar gaps pós-Sprint 3 — unificação ETL, testes skipped, docs, secrets operacionais e limpeza de legado.

**Pré-requisitos já feitos (não repetir):**
- Secrets validation (`check_secrets.py`, `docs/SECRETS.md`)
- ETL canônico declarado (`run_pipeline` + wrapper)
- Cobertura unitária extract/transform/load/run_pipeline (~83–94%)

---

## Epic A — ETL canônico (prioridade 1)

| ID | Título | Pontos | Prioridade | Depende |
|----|--------|--------|------------|---------|
| **UCM-27** | Unificar pipeline ETL: stub Prefect + deprecar paths paralelos + CI/docs | 5 | Critical | — |
| **UCM-28** | Remover módulos ETL legados após período de deprecação (process_data, load_data, validate_data, DataCleaner, PostgresLoader) | 3 | High | UCM-27 ✅ |
| **UCM-29** | Realinhar/remover testes skipped (`test_pipeline.py`, `test_db.py`) ao canônico | 3 | High | UCM-27 ✅ |

## Epic B — Qualidade & docs

| ID | Título | Pontos | Prioridade |
|----|--------|--------|------------|
| **UCM-30** | Atualizar README raiz (Python 3.11, arquitetura MLOps, link ETL/Secrets) | 2 | High | ✅ |
| **UCM-31** | Subir cobertura ETL e scripts MLOps para ≥70% nos módulos críticos | 5 | Medium |
| **UCM-32** | Flake8: limpar F401/E501 semânticos em `src/utils` (não cosmético W293) | 3 | Low |

## Epic C — Operação produção

| ID | Título | Pontos | Prioridade |
|----|--------|--------|------------|
| **UCM-33** | Checklist operacional: secrets GitHub configurados + dry-run `check_secrets` no CD | 2 | High |
| **UCM-34** | CD: staging → smoke → prod com rollback documentado/automático | 5 | High |
| **UCM-35** | Alertas Grafana (error_rate >5%, ETL failure) + runbook | 3 | Medium |

## Epic D — Limpeza legado

| ID | Título | Pontos | Prioridade |
|----|--------|--------|------------|
| **UCM-36** | Inventário e quarantine de scripts/ de análise sem testes (~15 arquivos) | 3 | Medium |
| **UCM-37** | Decidir destino Prefect: thin wrapper experimental **ou** remoção de `requirements-etl.txt` | 2 | Medium |
| **UCM-38** | Remover placeholder `src/used_cars/` se ainda existir; CODEOWNERS em `src/etl/` | 1 | Low |

---

## Ordem sugerida nesta sprint

```
UCM-27 ✅ → UCM-29 ✅ → UCM-30 ✅ → UCM-33 ✅ → UCM-34 ✅ → UCM-28 ✅
UCM-31 / UCM-35 / UCM-36 / UCM-37 em paralelo se houver capacidade
```

## Definição de pronto (Sprint 4)

- [x] Um único entrypoint ETL em CI e docs (UCM-27)
- [x] Zero testes skipped “pendente alinhamento” sem issue ou remoção (UCM-29)
- [x] README reflete stack atual (UCM-30)
- [x] `check_secrets --scope etl|api|cd` no caminho de deploy (UCM-33)
- [x] CD staging→prod descrito e testável (UCM-34)
- [x] UCM-28 — módulos ETL deprecated removidos

Import Jira: `jira_import_sprint4.csv`
