# Analise do Projeto de Contratos

## Resumo do projeto atual

O projeto atual e uma aplicacao FastAPI chamada `Contracts Intelligence`, com telas Jinja2, CSS/JavaScript puros e persistencia em PostgreSQL via SQLAlchemy/Alembic. O sistema ja possui uma base relevante para gestao de contratos hospitalares: login, usuarios, perfis, dashboard, cadastro/importacao de contratos, upload de documentos, extracao de texto, analise contratual local, comparacoes, aditivos e auditoria de autenticacao.

Nao ha frontend separado. A interface e renderizada pelo backend em `app/templates` e complementada por arquivos em `app/static`.

## Tecnologias encontradas

- Backend: Python 3.12, FastAPI, Starlette SessionMiddleware.
- Templates: Jinja2.
- Frontend: HTML, CSS e JavaScript puro.
- Graficos: Chart.js via CDN.
- Banco de dados: PostgreSQL com SQLAlchemy e Alembic.
- Upload/extracao: `python-multipart`, `pdfplumber`, `python-docx`, `pytesseract`, `pdf2image`, `pillow`.
- Seguranca: bcrypt para senhas, middleware CSRF, cabecalhos de seguranca, sessoes assinadas.
- Scripts: inicializacao, backup, restore, auditoria de seguranca e auditoria de persistencia.

## Estrutura geral de pastas

- `app/main.py`: aplicacao FastAPI, rotas HTML/API e regras de permissao.
- `app/models.py`: modelos SQLAlchemy.
- `app/schemas.py`: schemas Pydantic basicos.
- `app/services/`: autenticacao, upload, extracao, parser, scoring, comparacao e analise contratual.
- `app/templates/`: telas Jinja2.
- `app/static/css` e `app/static/js`: estilos e interacoes.
- `alembic/versions`: migrations.
- `scripts/`: start, backup, restore e auditorias.
- `docs/`: documentacao criada nesta analise.

## Models/tabelas existentes

- `access_profiles`
- `operators`
- `import_batches`
- `contracts`
- `contract_adjustments`
- `remuneration_tables`
- `remuneration_table_items`
- `materials_medicines_rules`
- `contract_events`
- `auth_audit_events`
- `imported_contract_records`
- `contract_files`
- `contract_additives`
- `ai_analyses`
- `contract_clauses`
- `contract_issues`
- `negotiation_opportunities`
- `negotiation_messages`
- `contract_comparisons`
- `contract_comparison_items`
- `users`

## Rotas/APIs existentes

- Autenticacao: `/login`, `/logout`, `/register`, `/change-password`.
- Usuarios: `/users`, `/users/new`, `/users/{id}/edit`, desativacao, reset de senha e promocao a admin.
- Perfis: `/access-profiles`, criacao, edicao e desativacao.
- Auditoria: `/auth-audit-events`.
- Dashboard: `/dashboard`.
- Contratos: `/contracts`, detalhe, edicao, eventos, exclusao e importacao.
- Cadastro adicional: `/contracts/{id}/additional`.
- Aditivos: `/aditivos`.
- Analise IA/local: `/analises-ia`, upload e reprocessamento.
- Comparacoes: `/comparacoes`.
- Saude: `/health`.

## Telas ja construidas

- Login/cadastro.
- Dashboard.
- Lista de contratos.
- Detalhe/edicao de contrato.
- Cadastro adicional de contrato.
- Aditivos.
- Analises por IA/local.
- Comparacoes.
- Auditoria de autenticacao.
- Usuarios.
- Perfis de acesso.
- Troca de senha.
- Erro 403/500.

## Sistema de login, autenticacao e perfis

O sistema usa sessao assinada, senhas com bcrypt e perfis armazenados em `access_profiles`. A criacao inicial de admin depende de `INITIAL_ADMIN_PASSWORD` no `.env`. Existem protecoes por perfil em varias rotas.

Perfis existentes antes da adaptacao:

- `Administrator`
- `Executive Board`
- `Contracts`
- `Financial`
- `Audit`
- `Read Only`

Para uso real no hospital, os nomes precisam ser padronizados em portugues do Brasil:

- Administrador
- Diretoria
- Contratos
- Financeiro
- Auditoria
- Somente leitura

## Migrations existentes

- `5bdcdc88aa12_initial.py`: cria schema a partir dos models.
- `d24610c09828_add_access_profiles_and_contract_.py`: adiciona perfis, ajustes, tabelas remuneratorias, regras de materiais/medicamentos e remove dados locais de teste.
- `f8a1c2d3e4b5_migrate_authentication_to_users.py`: cria auditoria de autenticacao e usuario admin inicial.

## Scripts existentes

- `Abrir Sistema.bat`
- `Atualizar Banco e GitHub.bat`
- `scripts/start_system.ps1`
- `scripts/start_system.bat`
- `scripts/start_contratos.vbs`
- `scripts/backup_database.bat`
- `scripts/restore_database.bat`
- `scripts/audit_security.py`
- `scripts/audit_persistence.py`

## Problemas encontrados

- Muitos textos antigos apresentavam problema de codificacao/mojibake em palavras acentuadas.
- Perfis estao em ingles, apesar da interface esperada em portugues do Brasil.
- Nao ha telas dedicadas para Operadoras, Condicoes Contratuais e Configuracoes.
- A auditoria existente esta concentrada em `auth_audit_events`; falta uma auditoria geral para acoes de negocio.
- O modulo de aditivos existe, mas nao ha tela dedicada para historico de reajustes.
- A estrutura de condicoes existe de forma parcial em tabelas remuneratorias e regras de materiais/medicamentos, mas falta uma entidade simples e direta para condicoes contratuais gerais.
- A exclusao de contratos e fisica; para uso real, o ideal e inativacao/status para preservar historico.
- Upload aceita apenas PDF/DOCX/TXT na camada de validacao, embora a tela mencione outros formatos.
- Ha dependencias externas via CDN para fontes e Chart.js, o que pode ser limitador em ambiente hospitalar restrito.
- O `git status` alertou problema com `index.lock`, que deve ser tratado com cuidado fora da aplicacao.

## Riscos tecnicos

- Migration inicial baseada em `Base.metadata.create_all()` reduz previsibilidade de diffs futuros.
- Algumas migrations usam SQL manual idempotente; isso ajuda em bancos existentes, mas exige revisao cuidadosa.
- A falta de auditoria geral dificulta rastreabilidade de edicoes contratuais.
- Exclusao fisica pode apagar historico relevante.
- A analise "IA" atual e local/regra heuristica; ela nao deve ser apresentada como resposta de IA externa.
- Problemas de codificacao podem passar para telas, logs e documentos.
- Rotas de permissao precisam cobrir os novos modulos para evitar exposicao indevida.

## O que ja esta pronto

- Base FastAPI organizada para rodar localmente no VSCode.
- PostgreSQL configurado.
- Migrations Alembic.
- Autenticacao com bcrypt.
- Sessoes e CSRF.
- Usuarios e perfis.
- Dashboard com dados reais do banco.
- Contratos com upload, edicao e detalhe.
- Documentos/anexos via `contract_files`.
- Aditivos via `contract_additives`.
- Reajustes via `contract_adjustments`.
- Comparacoes via `contract_comparisons`.
- Analise contratual local sem servico pago.
- Auditoria de autenticacao.
- Scripts de backup, restore e inicializacao.

## O que falta para uso real

- Padronizar perfis e textos em portugues do Brasil.
- Criar tela de Operadoras/Convenios.
- Criar tela de Condicoes Contratuais.
- Criar tela de Reajustes e Aditivos com historico consolidado.
- Criar auditoria geral de acoes de negocio.
- Incluir campos minimos de contrato: tipo, status, percentual de reajuste, data-base e observacoes.
- Incluir observacoes/status em operadoras.
- Melhorar dashboard para vencimentos em 30/60/90 dias, alertas de reajuste e documentacao pendente.
- Evitar exclusao fisica como fluxo principal.
- Ajustar comparacoes para enfatizar valores, prazos, reajustes, glosas e condicoes comerciais.
- Deixar claro que a analise atual e apoio local/regra heuristica, preparada para futura integracao.

## Plano de adaptacao

1. Criar migration incremental para campos faltantes, auditoria geral e condicoes contratuais.
2. Atualizar models mantendo as tabelas atuais.
3. Padronizar perfis em portugues e manter compatibilidade via migration.
4. Criar rotas/telas para Operadoras, Condicoes Contratuais, Reajustes e Aditivos, Auditoria geral e Configuracoes.
5. Ajustar menus para os modulos esperados.
6. Melhorar dashboard com metricas exigidas.
7. Registrar auditoria em login, logout, contratos, operadoras, reajustes, aditivos, condicoes e perfis.
8. Corrigir textos visiveis mais importantes para portugues do Brasil.
9. Executar validacoes possiveis localmente sem expor credenciais.

## Arquivos que precisam ser alterados

- `app/models.py`
- `app/main.py`
- `app/services/auth.py`
- `app/templates/base.html`
- `app/templates/dashboard.html`
- `app/templates/contracts.html`
- `app/templates/contract_detail.html`
- `app/templates/aditivos.html`
- `app/templates/analises_ia.html`
- `app/templates/comparacoes.html`
- `app/templates/auth_audit_events.html`
- `app/static/css/style.css`
- `alembic/versions/*.py`
- `README.md`
- `docs/RELATORIO_ADAPTACAO_CONTRATOS.md`

## Arquivos novos previstos

- `app/templates/operators.html`
- `app/templates/operator_form.html`
- `app/templates/contract_terms.html`
- `app/templates/adjustments.html`
- `app/templates/audit_logs.html`
- `app/templates/settings.html`
- Nova migration Alembic para adaptacao hospitalar.
