# Contracts Intelligence

Projeto FastAPI com login local e dashboard "Painel Executivo" para gestão de contratos com operadoras de saúde.

## Stack

- Python 3.12
- FastAPI
- Jinja2
- HTML, CSS e JavaScript puro
- Chart.js
- Sessões com `SessionMiddleware`

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

Instale as dependências:

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

## Como rodar em container

Crie um arquivo `.env` a partir do exemplo e ajuste pelo menos o segredo da sessao:

```powershell
Copy-Item .env.example .env
```

Suba a aplicacao em modo leve:

```powershell
docker compose up --build
```

Acesse:

```text
http://127.0.0.1:8000/login
```

Os dados ficam persistidos no volume Docker `contratos-data`, usando:

- banco: `/data/contracts.db`
- uploads: `/data/uploads/contracts`

Por padrao, o container nao instala OCR para ficar menor. Ele le PDF com texto, DOCX, TXT e MD. Para ler imagens ou PDFs escaneados, habilite OCR antes do build:

```powershell
$env:INSTALL_OCR="true"
docker compose up --build
```

Para parar:

```powershell
docker compose down
```

## Login padrão

- usuário: `admin`
- senha: `admin123`

Após login correto, o sistema redireciona para `/dashboard`.
