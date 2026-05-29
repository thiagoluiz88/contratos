# Contracts Intelligence

Projeto FastAPI com login local e dashboard "Painel Executivo" para gestÃ£o de contratos com operadoras de saÃºde.

## Stack

- Python 3.12
- FastAPI
- Jinja2
- HTML, CSS e JavaScript puro
- Chart.js
- SessÃµes com `SessionMiddleware`

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

Instale as dependÃªncias:

```powershell
python -m pip install -r requirements.txt
```

Execute o servidor:

```powershell
python -m uvicorn app.main:app --reload
```

Acesse:

```text
http://127.0.0.1:8000/login
```

## Login padrÃ£o

- usuÃ¡rio: `admin`
- senha: `admin123`

ApÃ³s login correto, o sistema redireciona para `/dashboard`.
