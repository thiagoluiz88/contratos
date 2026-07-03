# Relatorio de Adaptacao do Sistema de Contratos

## Arquivos alterados

- `app/main.py`
- `app/models.py`
- `app/services/auth.py`
- `app/templates/base.html`
- `app/templates/users.html`
- `app/templates/access_profiles.html`
- `app/templates/contract_detail.html`
- `app/templates/dashboard.html`
- `app/templates/contract_terms.html`
- `app/services/document_processing_service.py`
- `app/services/contract_ai_analysis_service.py`
- `app/templates/document_detail.html`
- `app/templates/document_validate.html`
- `app/static/css/style.css`
- `docs/ANALISE_PROJETO_CONTRATOS.md`
- `docs/ESCOPO_GERAL_SISTEMA_CONTRATOS.md`
- `docs/MODULO_1_IA_EXTRACAO.md`

## Arquivos criados

- `docs/ANALISE_PROJETO_CONTRATOS.md`
- `docs/RELATORIO_ADAPTACAO_CONTRATOS.md`
- `app/templates/operators.html`
- `app/templates/operator_form.html`
- `app/templates/contract_terms.html`
- `app/templates/adjustments.html`
- `app/templates/audit_logs.html`
- `app/templates/settings.html`
- `app/templates/documents.html`
- `app/templates/document_detail.html`
- `app/templates/document_validate.html`
- `docs/MODULO_1_IA_EXTRACAO.md`

## Migration criada

- `alembic/versions/9c7b4a1d2e6f_hospital_contract_management.py`
- `alembic/versions/2f4c8a9b1d3e_add_document_extractions.py`
- `alembic/versions/7b6e2c4f9a10_normalize_document_status_defaults.py`
- `alembic/versions/3a5d7e9c2b41_add_raw_extraction_text_fields.py`

## Funcionalidades adicionadas

- Modulo de Operadoras/Convenios com nome, CNPJ, contato, e-mail, telefone, observacoes e status.
- Modulo de Condicoes Contratuais para diarias, taxas, pacotes, materiais, medicamentos, OPME, honorarios, autorizacoes, glosas e prazos.
- Modulo consolidado de Reajustes e Aditivos com historico de reajustes, indice aplicado, percentual, data, justificativa e status.
- Auditoria geral em `audit_logs`, separada da auditoria de autenticacao ja existente.
- Tela de Configuracoes com resumo dos parametros operacionais.
- Novos campos de contrato: tipo, status, percentual de reajuste, data-base e observacoes.
- Estrutura de contrato mae/aditivo filho preparada com `contracts.parent_contract_id`.
- Versionamento de condicoes contratuais preparado em `contract_terms`.
- Base futura de documentos/anexos preparada usando a tabela existente `contract_files`.
- Novo campo de observacoes em operadoras.
- Registro de auditoria para login, falha de login, logout, usuarios, perfis, edicao/inativacao de contrato, upload de documento, operadoras, condicoes e reajustes.
- Inativacao de contrato no lugar de exclusao fisica pela rota antiga.
- Perfis padronizados em portugues na camada de autenticacao: Administrador, Diretoria, Contratos, Financeiro, Auditoria e Somente leitura.
- Dashboard ampliado com vencimentos em 60/90 dias e documentacao pendente.
- Modulo 1 iniciado com fluxo funcional de Documentos e Extracao.
- Estrutura `contract_extractions` criada para dados estruturados pendentes de validacao.
- Upload de documentos com validacao de extensao, limite de tamanho e nome interno seguro.
- Tela de validacao humana lado a lado criada.
- Aprovacao e rejeicao de extracao implementadas sem aplicar automaticamente dados ao cadastro.
- Extracao real de texto bruto implementada para PDF com camada digital e DOCX.
- OCR local preparado para PNG/JPG/JPEG e PDF escaneado quando Tesseract/Poppler estiverem configurados.
- DOC legado aceito no upload, mas marcado como pendente de conversao para extracao automatica.
- Tela de detalhe do documento exibe metodo de extracao, paginas, caracteres, avisos e previa do texto.
- Tela de validacao humana exibe previa do texto extraido no lado esquerdo.
- Servico futuro `contract_ai_analysis_service.py` criado sem IA real, retornando apenas status `pendente_integracao_ia`.

## Funcionalidades corrigidas ou preservadas

- PostgreSQL foi mantido como banco configurado.
- Autenticacao, usuarios, perfis e auditoria existente foram preservados.
- A estrutura de upload/anexos existente foi mantida.
- Analise contratual local foi preservada sem integracao paga ou externa.
- Comparacoes existentes foram mantidas.
- Aditivos antigos foram preservados e ganharam entrada consolidada em Reajustes e Aditivos.

## Resultado da validacao do banco

- `.env` existente e validado sem exposicao de credenciais.
- Sistema confirmado em PostgreSQL.
- `alembic current` antes da rodada: `f8a1c2d3e4b5`.
- `alembic heads`: `3a5d7e9c2b41`.
- `alembic upgrade head`: executado com sucesso.
- `alembic current` apos upgrade: `3a5d7e9c2b41 (head)`.
- `python -m app.init_db`: executado com sucesso.
- Tabelas conferidas por introspeccao: `contracts`, `operators`, `contract_terms`, `contract_files`, `contract_extractions`, `contract_adjustments`, `contract_additives`, `audit_logs`, `users`, `access_profiles`.

## Correcoes de mojibake

- Varredura realizada em Python, templates, JS, servicos e docs.
- Menus e labels principais revisados para portugues do Brasil.
- Referencias visiveis antigas a perfis em ingles ajustadas para `Administrador` e `Somente leitura`.
- Nao foram alteradas strings historicas em migrations antigas, pois elas documentam estados anteriores do banco.

## Estruturas preparadas nesta rodada

- Contrato mae/aditivo filho: `contracts.parent_contract_id`, relacionamento self-referenciado no model e exibicao basica no detalhe do contrato.
- Versionamento de tabelas: `contract_terms.version`, `valid_from`, `valid_until`, `is_current`, `source_type`, `source_document_id`.
- Documentos/anexos: `contract_files.processing_status`, `processed_at`, `notes`, `error_message`, mantendo a tabela existente para evitar duplicidade.
- Auditoria: eventos adicionados para usuarios, perfis, upload de documento, criacao/edicao de condicoes e criacao/edicao de reajustes.
- Rotas: adicionado alias `/comparisons` para o modulo existente `/comparacoes`.
- Rotas de documentos criadas: `/documents`, `/documents/upload`, `/documents/{id}`, `/documents/{id}/download`, `/documents/{id}/validate`, `/documents/{id}/approve`, `/documents/{id}/reject`.

## Problemas encontrados

- A migration inicial usa `Base.metadata.create_all()`, o que reduz previsibilidade historica do schema.
- O ambiente Python global nao tinha `psycopg2`; o import funcionou usando `.venv`.
- A execucao de `compileall` foi bloqueada por permissao em `__pycache__`; a validacao AST sem escrita passou.
- Verificacao visual em navegador real nao foi executada; a validacao foi feita por `TestClient` e parsing de templates.
- Dois arquivos temporarios gerados no teste em `.codex-run/test-uploads` ficaram bloqueados para exclusao pelo Windows/sandbox. Os registros temporarios correspondentes foram removidos do banco.
- O Modulo 1 ainda nao executa IA real nem extracao interpretativa definitiva. OCR local so executa quando Tesseract/Poppler estiverem configurados no ambiente.
- Na rodada de texto bruto, os parsers foram fechados com context managers, mas arquivos temporarios gerados em `.codex-run/text-extraction-uploads` tambem ficaram bloqueados para exclusao pelo Windows/sandbox. Registros temporarios foram removidos do banco.

## Como rodar o projeto

1. Configure `.env` local com PostgreSQL, `APP_SECRET`, `DB_PASSWORD` e `INITIAL_ADMIN_PASSWORD`.
2. Ative a venv:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Aplique migrations:

```powershell
python -m app.init_db
```

4. Inicie o sistema:

```powershell
.\scripts\start_system.ps1
```

5. Acesse a URL informada pelo script, normalmente `http://127.0.0.1:8000/login`.

## Como testar

- Login com o usuario administrador.
- Acessar Dashboard.
- Cadastrar uma operadora em `/operators`.
- Importar ou editar um contrato em `/contracts`.
- Editar contrato e preencher tipo, status, responsavel, reajuste, data-base e observacoes.
- Registrar condicao em `/contract-terms`.
- Registrar reajuste em `/adjustments`.
- Conferir aditivos no mesmo modulo.
- Criar uma comparacao em `/comparacoes`.
- Acessar Analise IA em `/analises-ia`.
- Enviar documento em `/documents`.
- Validar campos em `/documents/{id}/validate`.
- Aprovar em `/documents/{id}/approve`.
- Rejeitar em `/documents/{id}/reject`.
- Conferir auditoria geral em `/audit-logs`.
- Conferir eventos de autenticacao em `/auth-audit-events`.
- Validar permissoes com perfis Administrador, Diretoria, Contratos, Financeiro, Auditoria e Somente leitura.

## Validacoes executadas

- Validacao AST dos arquivos Python sem gerar bytecode:

```text
python_ast_ok
```

- Import da aplicacao com a venv:

```text
app_import_ok
```

- Conferencia das rotas registradas confirmou os novos modulos:

```text
/operators
/contract-terms
/adjustments
/audit-logs
/settings
```

- Parsing dos templates Jinja:

```text
templates_ok
```

- Health check e rotas principais via `TestClient`:

```text
health 200 ok
/ 303 /login
/login 200
/dashboard 303 /login
/contracts 303 /login
/operators 303 /login
/contract-terms 303 /login
/adjustments 303 /login
/comparisons 303 /comparacoes
/documents 303 /login
/audit-logs 303 /login
/settings 303 /login
```

- Testes funcionais de extracao de texto bruto:

```text
pdf_upload 303 /documents/{id}/validate
docx_upload 303 /documents/{id}/validate
png_upload 303 /documents/{id}/validate
blocked_upload 400
download 200
detail 200
validate_docx 200 True
approve_pdf 303
reject_png 303
doc contrato.pdf aprovado aprovado pdf_text 18 True False
doc contrato.docx aguardando_validacao texto_extraido docx 32 True False
doc imagem.png rejeitado rejeitado image_ocr_unavailable 0 False True
audit_events_created 21
```

Interpretacao:

- PDF com texto digital extraiu texto via `pdf_text`.
- DOCX extraiu paragrafo e tabela via `docx`.
- PNG sem OCR local configurado nao quebrou o fluxo e registrou aviso.
- Extensao invalida foi bloqueada.
- Download autenticado funcionou.

- Testes funcionais de documentos:

```text
login 200
route /documents 200
route /documents/upload 405
route /documents/1 303
route /documents/1/validate 303
blocked_upload 400
allowed_upload 303 /documents/{id}/validate
validate_get 200
validate_save 303
approve 303
second_upload 303
reject 303
contract_files_created 2
extractions_created 2
audit_events_created 12
```

Os registros temporarios de banco criados para teste foram removidos ao final.

## Comandos executados

```powershell
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.init_db
```

Tambem foram executadas validacoes locais com AST, import da aplicacao, parsing Jinja, introspeccao de tabelas e `TestClient`.

## Proximos passos recomendados

- Criar testes automatizados com banco de teste PostgreSQL.
- Evoluir permissoes por acao, nao apenas por tela.
- Ampliar comparacoes para destacar diferenca monetaria por item de condicao contratual.
- Proxima etapa recomendada: integrar OCR/parser real ao `document_processing_service.py`, mantendo validacao humana obrigatoria antes de aplicar dados em `contracts` e `contract_terms`.
- Proxima etapa recomendada: integrar IA interpretativa para identificar valores, prazos, indices, clausulas criticas e condicoes contratuais, mantendo validacao humana antes de aplicar dados no banco.
