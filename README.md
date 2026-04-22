# Contracts Intelligence

Sistema web para leitura, cadastro, revisao e acompanhamento de contratos entre hospital e operadoras de saude.

## Visao geral

O projeto foi construido com:

- `FastAPI` para a aplicacao web
- `Jinja2` para renderizacao das telas
- `SQLAlchemy` para persistencia local
- `SQLite` como banco padrao
- `Chart.js` para os graficos do dashboard

## Principais recursos

- Dashboard executivo com foco em risco, score e vencimento
- Upload de arquivos `PDF`, `DOCX`, `TXT` e `MD`
- OCR para PDF escaneado
- Extracao automatica de dados contratuais
- Edicao manual dos campos extraidos
- Score contratual com classificacao e alertas
- Historico de eventos, aditivos e notas
- Comparacao entre contratos
- Exportacao em `CSV`, `XLSX` e `PDF`
- Login local simples

## Estrutura do projeto

```text
contract_system/
├── app/
│   ├── services/
│   ├── static/
│   ├── templates/
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── schemas.py
├── uploads/
├── contracts.db
├── requirements.txt
└── README.md
```

## Requisitos

- Python 3.12+ recomendado
- Git
- Tesseract OCR instalado no sistema se voce quiser OCR em PDFs escaneados

## Configuracao do ambiente

1. Clone o repositorio:

```bash
git clone https://github.com/thiagoluiz88/contratos.git
cd contratos
```

2. Crie o ambiente virtual:

```bash
python -m venv .venv
```

3. Ative o ambiente virtual:

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Windows CMD:

```bat
.venv\Scripts\activate.bat
```

Linux/macOS:

```bash
source .venv/bin/activate
```

4. Instale as dependencias:

```bash
pip install -r requirements.txt
```

5. Copie o arquivo de ambiente:

```bash
copy .env.example .env
```

No Linux/macOS:

```bash
cp .env.example .env
```

## Variaveis de ambiente

O projeto atualmente usa estas variaveis:

- `APP_USER`: usuario do login local
- `APP_PASSWORD`: senha do login local
- `APP_SECRET`: chave usada pela sessao

Consulte o arquivo `.env.example` para um modelo inicial.

## Como rodar

Com o ambiente virtual ativo:

```bash
uvicorn app.main:app --reload
```

Depois acesse:

- `http://127.0.0.1:8000/login`

## Login padrao

Se voce nao definir variaveis de ambiente:

- Usuario: `admin`
- Senha: `admin123`

## Fluxo de uso

1. Faça login no sistema
2. Envie um contrato pela tela de upload
3. Revise os campos extraidos automaticamente
4. Consulte score, risco, vigencia e alertas
5. Registre eventos e acompanhe vencimentos
6. Exporte dados quando necessario

## Observacoes importantes

- O banco local padrao e o arquivo `contracts.db`
- A pasta `uploads/` armazena os arquivos enviados
- O parser contratual e heuristico; sempre revise os dados antes de uso operacional ou juridico
- Se voce tiver um banco antigo com estrutura diferente, pode ser necessario remover o `contracts.db` antes de subir a aplicacao novamente

## Publicacao no GitHub

Este projeto esta conectado ao repositorio:

- `https://github.com/thiagoluiz88/contratos`

Fluxo basico para enviar novas alteracoes:

```bash
git add .
git commit -m "Sua mensagem"
git push
```

## Melhorias futuras sugeridas

- suporte formal a `.env` com `python-dotenv`
- configuracao de banco por variavel de ambiente
- testes automatizados
- pipeline de deploy
- controle de usuarios mais robusto
