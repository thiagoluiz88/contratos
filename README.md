# Contracts Intelligence

Projeto FastAPI com login local e dashboard "Painel Executivo" para gestão de contratos com operadoras de saúde.

## Stack

- Python 3.12
- FastAPI
- Jinja2
- HTML, CSS e JavaScript puro
- Chart.js
- Sessoes com `SessionMiddleware`
- PostgreSQL via SQLAlchemy e Alembic

## Estrutura

```text
app/
  main.py
  templates/
    base.html
    login.html
    dashboard.html
  static/
    css/
      style.css
    js/
      dashboard.js
requirements.txt
README.md
```

## Como rodar

Crie o ambiente virtual:

```powershell
python -m venv .venv
```

Ative o ambiente:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instale as dependencias:

```powershell
python -m pip install -r requirements.txt
```

Configure o PostgreSQL local no arquivo `.env`:

```text
DB_HOST=localhost
DB_PORT=5432
DB_NAME=contratos_db
DB_USER=postgres
DB_PASSWORD=sua_senha_local
APP_SECRET=uma-chave-aleatoria-com-pelo-menos-32-caracteres
INITIAL_ADMIN_PASSWORD=uma-senha-forte-para-a-criacao-inicial
ENABLE_SELF_REGISTRATION=false
APP_HOST=127.0.0.1
APP_PORT=8000
APP_PUBLIC_HOST=127.0.0.1
```

Crie o banco, aplique migrations e garanta os perfis minimos:

```powershell
python -m app.init_db
```

Ou aplique migrations com Alembic:

```powershell
python -m alembic upgrade head
```

Execute o servidor:

```powershell
.\scripts\start_system.ps1
```

Acesse:

```text
O script informa a URL de login, por exemplo: http://127.0.0.1:8000/login
```

Para execucao manual, use o Uvicorn sem `--reload`:

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Acesso na rede interna

Por padrao o sistema escuta apenas em `127.0.0.1`. Para acesso por colaboradores na rede interna, configure no `.env`:

```text
APP_HOST=0.0.0.0
APP_PORT=8000
APP_PUBLIC_HOST=IP_OU_NOME_DO_SERVIDOR
SESSION_HTTPS_ONLY=false
```

Para usar a porta `5173`, altere apenas:

```text
APP_PORT=5173
APP_PUBLIC_HOST=IP_OU_NOME_DO_SERVIDOR
```

Use essa configuracao somente em rede confiavel. Para producao ou exposicao fora da maquina local, coloque HTTPS/proxy reverso, habilite `SESSION_HTTPS_ONLY=true` e revise firewall, backup e permissoes.

## Verificações de segurança

Execute as auditorias locais:

```powershell
.\.venv\Scripts\python.exe -m scripts.audit_security
.\.venv\Scripts\python.exe -m scripts.audit_persistence
```

Em execucao local, mantenha `APP_HOST=127.0.0.1`. Para rede interna, use a secao acima e controles adicionais.

## Login inicial

A migration de autenticação cria o usuário administrador inicial `admin` com senha armazenada em hash bcrypt.
Altere a senha inicial antes de usar o sistema em producao.

Apos login correto, o sistema redireciona para `/dashboard`.

## Scripts uteis

- `Abrir Sistema.bat`: prepara o banco, sobe o servidor e abre o login.
- `Atualizar Banco e GitHub.bat`: executa backup, migrations, auditorias e fluxo seguro de Git.
- `scripts\backup_database.bat`: gera backup PostgreSQL em `backups/`.
- `scripts\restore_database.bat caminho\backup.dump`: restaura backup com confirmacao manual.
