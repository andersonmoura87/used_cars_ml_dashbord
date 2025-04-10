# Guia de Contribuição

Obrigado pelo seu interesse em contribuir com o Sistema de Análise de Veículos Usados! Este documento fornece diretrizes e instruções para contribuir com o projeto.

## Índice

- [Código de Conduta](#código-de-conduta)
- [Como Contribuir](#como-contribuir)
- [Ambiente de Desenvolvimento](#ambiente-de-desenvolvimento)
- [Padrões de Código](#padrões-de-código)
- [Testes](#testes)
- [Documentação](#documentação)
- [Processo de Pull Request](#processo-de-pull-request)

## Código de Conduta

Este projeto e todos os participantes estão sujeitos ao [Código de Conduta](CODE_OF_CONDUCT.md). Ao participar, você concorda em manter este código.

## Como Contribuir

1. Faça um fork do repositório
2. Crie uma branch para sua feature (`git checkout -b feature/AmazingFeature`)
3. Commit suas mudanças (`git commit -m 'Add some AmazingFeature'`)
4. Push para a branch (`git push origin feature/AmazingFeature`)
5. Abra um Pull Request

## Ambiente de Desenvolvimento

### Pré-requisitos

- Python 3.8+
- PostgreSQL
- Redis
- Git

### Configuração

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/seu-repositorio.git
cd seu-repositorio
```

2. Crie e ative o ambiente virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Instale as dependências:
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Para desenvolvimento
```

4. Configure as variáveis de ambiente:
```bash
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

5. Configure o banco de dados:
```bash
python scripts/setup_dev.py
```

## Padrões de Código

### Python

- Seguimos o [PEP 8](https://www.python.org/dev/peps/pep-0008/)
- Use type hints
- Documente funções e classes com docstrings
- Mantenha as funções pequenas e focadas
- Use nomes descritivos para variáveis e funções

### SQL

- Use nomes descritivos para tabelas e colunas
- Adicione comentários para queries complexas
- Mantenha as queries otimizadas
- Use índices apropriadamente

### Git

- Use mensagens de commit descritivas
- Faça commits pequenos e focados
- Mantenha a branch principal sempre estável
- Use branches para features e correções

## Testes

### Executando Testes

```bash
# Executar todos os testes
pytest

# Executar testes específicos
pytest tests/test_etl.py

# Executar testes com cobertura
pytest --cov=src tests/
```

### Escrevendo Testes

- Crie testes para novas funcionalidades
- Mantenha a cobertura de testes acima de 80%
- Use fixtures do pytest para setup comum
- Teste casos de erro e edge cases

## Documentação

### Código

- Use docstrings para documentar funções e classes
- Mantenha os comentários atualizados
- Documente decisões importantes
- Use type hints para melhor documentação

### API

- Documente todos os endpoints
- Inclua exemplos de uso
- Documente parâmetros e respostas
- Mantenha a documentação atualizada

### README e Documentação Geral

- Mantenha o README atualizado
- Documente mudanças importantes
- Inclua exemplos de uso
- Mantenha a documentação clara e concisa

## Processo de Pull Request

1. Certifique-se de que seu código segue os padrões
2. Execute todos os testes
3. Atualize a documentação se necessário
4. Crie um Pull Request com uma descrição clara
5. Aguarde a revisão e feedback
6. Faça as alterações solicitadas se necessário
7. Aguarde a aprovação e merge

### Template de Pull Request

```markdown
## Descrição
[Descreva as mudanças feitas]

## Tipo de Mudança
- [ ] Bug fix
- [ ] Nova feature
- [ ] Melhoria de performance
- [ ] Documentação
- [ ] Outro

## Checklist
- [ ] Testes adicionados/atualizados
- [ ] Documentação atualizada
- [ ] Código segue os padrões
- [ ] Todos os testes passam
- [ ] Branch atualizada com a principal

## Screenshots (se aplicável)
[Adicione screenshots aqui]

## Notas Adicionais
[Adicione notas adicionais aqui]
``` 