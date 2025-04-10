# Sandbox - Ambiente de Desenvolvimento e Testes

Este diretório contém scripts e recursos para desenvolvimento, testes e experimentação.

## Estrutura

```
sandbox/
├── data/               # Dados de teste e experimentação
├── notebooks/          # Jupyter notebooks para análise exploratória
├── scripts/            # Scripts de desenvolvimento e teste
└── tests/             # Testes unitários e de integração
```

## Scripts Disponíveis

### Desenvolvimento
- `scripts/dev_setup.py`: Configuração do ambiente de desenvolvimento
- `scripts/dev_db.py`: Scripts para manipulação do banco de dados de desenvolvimento

### Testes
- `scripts/test_data_generator.py`: Gera dados sintéticos para testes
- `scripts/test_quality.py`: Testes de qualidade de dados

### Experimentação
- `scripts/experiment_ml.py`: Experimentos com modelos de ML
- `scripts/experiment_viz.py`: Experimentos com visualizações

## Banco de Dados

### Desenvolvimento
- Nome: `mobato_dev`
- Usuário: `dev_user`
- Senha: `dev_password`
- Host: `localhost`
- Porta: `5432`

### Testes
- Nome: `mobato_test`
- Usuário: `test_user`
- Senha: `test_password`
- Host: `localhost`
- Porta: `5432`

## Como Usar

1. Ative o ambiente virtual:
```bash
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Instale as dependências de desenvolvimento:
```bash
pip install -r requirements-dev.txt
```

3. Configure o banco de dados de desenvolvimento:
```bash
python sandbox/scripts/dev_setup.py
```

4. Execute os testes:
```bash
python -m pytest sandbox/tests/
``` 