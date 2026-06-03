# Security Policy

## Versões suportadas

| Versão | Suporte de segurança |
|--------|----------------------|
| `main` | ✅ Ativo              |
| Tags antigas | ❌ Sem suporte  |

## Reportar uma vulnerabilidade

**NÃO abra uma issue pública** para vulnerabilidades de segurança.

### Como reportar

1. Envie um e-mail para o mantenedor com o assunto `[SECURITY] used-cars-ml — <breve descrição>`
2. Inclua:
   - Descrição da vulnerabilidade
   - Passos para reproduzir
   - Impacto estimado (confidencialidade, integridade, disponibilidade)
   - Versão/commit afetado
   - Sugestão de correção (opcional)

### Prazo de resposta

- **Acuse de recebimento**: até 48 horas
- **Confirmação da vulnerabilidade**: até 7 dias
- **Correção e release**: até 30 dias (dependendo da severidade)

### Política de disclosure

Seguimos **Responsible Disclosure** (divulgação coordenada):
- Não publicamos detalhes da vulnerabilidade enquanto o fix não estiver disponível.
- Após o patch, publicamos um advisory com crédito ao reporter (se desejado).
- CVEs críticos podem ter prazo acelerado.

## Escopo

Estão **no escopo**:
- API FastAPI (`src/api/`)
- Autenticação e autorização
- Injeção de dados (SQL, shell)
- Exposição de credenciais/secrets
- Containers Docker e imagens base
- Dependências com CVEs conhecidos

Estão **fora do escopo**:
- Issues em infra de terceiros (GH Actions, DockerHub)
- Bugs de usabilidade sem impacto de segurança
- Vulnerabilidades em ambientes de desenvolvimento local sem rede

## Boas práticas adotadas

- Autenticação via `X-API-Key` com comparação constant-time
- Usuário não-root nos containers
- Multi-stage build sem ferramentas de compilação na imagem final
- CORS restrito sem wildcard
- Rate limiting via `slowapi`
- Security headers HTTP em todas as respostas
- Secrets via variáveis de ambiente (nunca hardcoded)
- Dependabot habilitado para Python, Docker e GitHub Actions
