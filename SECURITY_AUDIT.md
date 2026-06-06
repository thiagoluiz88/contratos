# Auditoria de segurança local

Data: 06/06/2026
Referência: boas práticas OWASP para autenticação, sessão, autorização, upload, CSRF, XSS, erros e segredos.

## Vulnerabilidades encontradas e corrigidas

- `APP_SECRET` possuía valor local fraco/previsível. Foi substituída por chave criptográfica de 64 caracteres no `.env` ignorado.
- Sessão não tinha expiração explícita. Agora expira após 8 horas e usa `HttpOnly` e `SameSite=Lax`.
- Rotas confiavam no perfil armazenado no cookie. Usuário e perfil agora são revalidados no PostgreSQL em cada acesso protegido.
- Não havia proteção CSRF. Foi adicionada validação de origem/token para métodos mutáveis.
- Senhas aceitavam apenas 8 caracteres. Agora exigem 10 caracteres, maiúscula, minúscula, número e caractere especial.
- Criação inicial usava hash administrativo fixo no código. Agora exige `INITIAL_ADMIN_PASSWORD` forte no `.env`.
- Upload aceitava formatos amplos e tamanho ilimitado. Agora aceita somente PDF, DOCX e TXT, limita a 20 MB, usa UUID, basename seguro e valida assinatura/conteúdo.
- Respostas de erro expunham detalhes SQL. Detalhes internos foram removidos das respostas.
- Não havia página amigável para erro 500 nem log rotativo local. Ambos foram adicionados.
- Dados pessoais desnecessários foram removidos do cookie de sessão.
- Logs genéricos agora também são ignorados pelo Git.

## Controles confirmados

- Hash de senha: bcrypt com custo 12.
- Login bloqueia usuário inativo e perfil inativo.
- Login, logout, falhas e ações importantes são persistidos em `auth_audit_events`.
- Logout limpa toda a sessão.
- Autorizações sensíveis são verificadas no backend.
- Read Only não pode criar, editar ou excluir.
- SQL dinâmico usa SQLAlchemy/parâmetros; os SQLs brutos encontrados são estáticos ou parametrizados.
- Jinja mantém autoescape; nenhum uso de `|safe`, `Markup` ou `mark_safe` foi encontrado.
- `.env`, uploads, backups, logs e banco local estão ignorados pelo Git.
- Lançadores normais usam `127.0.0.1`, sem `0.0.0.0` e sem `--reload`.
- `pip-audit -r requirements.txt`: nenhuma vulnerabilidade conhecida encontrada.

## Testes obrigatórios executados

Comando:

```powershell
.\.venv\Scripts\python.exe -m scripts.audit_security
```

Resultado: `AUDITORIA DE SEGURANCA: OK`

Casos validados:

- Usuário sem login não acessa páginas internas.
- Read Only não cria, edita ou exclui contratos.
- Contracts e Audit não acessam usuários ou perfis.
- Financial não acessa auditoria.
- Usuário inativo e perfil inativo não autenticam.
- Senha fraca é bloqueada.
- Requisição POST sem origem/token CSRF é bloqueada.
- Upload `.exe`, arquivo acima de 20 MB e conteúdo inválido são bloqueados.
- Nome com path traversal é reduzido a basename e salvo dentro de `uploads/contracts`.
- Cookie possui `HttpOnly`, `SameSite=Lax` e expiração.
- `.env` permanece ignorado.
- Execução local permanece configurada para `127.0.0.1`.
- Uvicorn foi iniciado temporariamente em `127.0.0.1:8099`, respondeu ao `/health` e foi encerrado após o teste.

Testes complementares:

```powershell
.\.venv\Scripts\python.exe -m scripts.audit_persistence
.\.venv\Scripts\python.exe -m app.db_checks
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt
```

Todos passaram.

## Riscos pendentes e recomendações

- `SESSION_HTTPS_ONLY=false` é necessário para HTTP local. Caso o sistema seja exposto, habilitar HTTPS e `SESSION_HTTPS_ONLY=true`.
- A CSP ainda permite scripts e estilos inline por compatibilidade com as telas legadas. Migrar scripts inline para arquivos locais permitirá remover `unsafe-inline`.
- Não há antivírus/sandbox para analisar PDFs e DOCX. Manter uso local e importar apenas arquivos confiáveis.
- Dependências diretas ainda não estão fixadas em versões exatas. Criar lockfile antes de distribuição para outras máquinas.
- O logout continua disponível por GET para compatibilidade com o lançador que força nova autenticação.
- Recomenda-se alterar imediatamente a senha de qualquer administrador criado antes desta auditoria.
- O sistema não deve ser exposto em rede sem HTTPS, proxy reverso, rate limiting e revisão adicional.

## Arquivos principais alterados

- `app/config.py`
- `app/security.py`
- `app/main.py`
- `app/services/auth.py`
- `app/services/uploads.py`
- `app/templates/base.html`
- `app/templates/login.html`
- `app/templates/error_500.html`
- `app/static/js/security.js`
- `.env.example`
- `.gitignore`
- `scripts/audit_security.py`
- `README.md`

Nenhum push foi realizado.
