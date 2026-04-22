# Contracts Intelligence - Sistema de Análise Contratual Hospitalar

Sistema web local para leitura, cadastro e análise de contratos entre hospital e operadoras de saúde.

## Recursos principais
- Dashboard executivo com gráficos
- Upload de PDF, DOCX, TXT e MD
- OCR automático para PDF escaneado
- Cadastro automático de contratos
- Edição manual dos campos extraídos
- Score contratual e alertas
- Comparação entre contratos
- Histórico de aditivos, notas e renegociações
- Exportação em CSV, Excel e PDF
- Login simples local

## Login padrão
- Usuário: `admin`
- Senha: `admin123`

Você pode alterar com variáveis de ambiente:
- `APP_USER`
- `APP_PASSWORD`
- `APP_SECRET`

## Como rodar
```bash
cd contract_system
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

Acesse:
- `http://127.0.0.1:8000/login`

## Observações
- Se você já tiver um `contracts.db` antigo com outro layout de colunas, apague esse arquivo antes de rodar a nova versão.
- O OCR depende do Tesseract instalado no sistema operacional. No ambiente desta entrega ele já foi previsto no código.
- O parser contratual é heurístico. Sempre revise os dados extraídos antes de usar em decisão contratual.
