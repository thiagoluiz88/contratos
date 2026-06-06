# Contracts Intelligence

Projeto FastAPI com login local e dashboard "Painel Executivo" para gestão de contratos com operadoras de saúde.

## Stack

- Python 3.12
- FastAPI
- Jinja2
- HTML, CSS e JavaScript puro
- Chart.js
- Sessoes com `SessionMiddleware`

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
```

Crie as tabelas:

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

## Login inicial

A migration de autenticação cria o usuário administrador inicial `admin` com senha armazenada em hash bcrypt.
Altere a senha inicial antes de usar o sistema em producao.

Apos login correto, o sistema redireciona para `/dashboard`.
