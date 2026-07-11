# Testes Automatizados

## Objetivo

A suite protege os fluxos de simulacao, versionamento oficial, referencias, aplicacao de extracao aprovada, permissoes, auditoria e rotas principais. Nenhum teste chama API externa ou depende de internet.

## Pre-requisitos

- ambiente virtual criado e dependencias de `requirements.txt` instaladas;
- PostgreSQL configurado pelas variaveis locais normais da aplicacao;
- banco atualizado no head do Alembic;
- perfis padrao criados por `python -m app.init_db`.

## Seguranca dos dados

O projeto ainda usa o PostgreSQL indicado por `DATABASE_URL`; nao existe banco de teste separado provisionado automaticamente. Os testes de integracao criam registros com marcador UUID `PYTEST-*` e executam limpeza explicita ao final.

Recomenda-se configurar um banco PostgreSQL exclusivo para testes antes de executar a suite em CI. Nunca aponte testes para uma instancia compartilhada sem backup e sem revisar `DATABASE_URL`. Credenciais nao ficam hardcoded nos testes.

## Comandos

```powershell
python -m pytest
python -m pytest tests/test_contract_terms_simulations.py
python -m pytest tests/test_reference_tables.py
python -m pytest tests/test_documents_apply_flow.py
python -m pytest tests/test_audit_logs.py
python -m pytest tests/test_routes.py
python -m pytest tests/test_commercial_bi.py
python -m pytest tests/test_production_imports.py
python -m pytest tests/test_financial_impact_service.py
python -m pytest tests/test_production_layouts.py
python -m pytest tests/test_contract_term_pricing.py
python -m pytest tests/test_production_import_preview.py
python -m pytest tests/test_cost_allocation.py
python -m app.db_checks
python -m scripts.audit_security
python -m scripts.audit_persistence
python -m scripts.run_quality_checks
```

No Windows, substitua `python` por `.\.venv\Scripts\python.exe` quando o ambiente virtual nao estiver ativado.

## Cobertura funcional

- comparacao: sem alteracao, novo, removido, aumento, reducao e vigencia;
- pendencias e descarte de item invalido na aplicacao;
- aprovacao, aplicacao, encerramento da versao anterior e preservacao historica;
- bloqueios sem aprovacao, duplicado, contrato divergente, inexistentes e cancelamento posterior;
- proibicao para perfil Somente leitura;
- referencias vazias e com classificacoes acima, abaixo, igual e sem referencia;
- extracao aprovada, operadora por CNPJ, nao sobrescrita de campo preenchido e `apply_summary`;
- audit logs essenciais;
- health check, autenticacao e paginas do Modulo 2.
- BI Comercial: resumo, ranking, extremos por categoria, referências, comparação executiva, CSV, permissões e auditoria.
- produção e custos: lote, CSV válido/pendente, vínculos, totais, hash de paciente, reprocessamento, cancelamento, rotas, permissões, auditoria e exportação;
- impacto financeiro: receita contratual estimada, reajuste aritmético, simulação ponderada, margem bruta estimada e insuficiência de volume/custo.
- layouts: validação, mapeamento, aliases, colunas ignoradas, CSV, Excel, permissões e auditoria;
- precificação histórica: seleção por vigência, preço por item e pendências sem versão/dados.
- preview efêmero: CSV, Excel, campos ausentes, arquivo inválido, não persistência, permissões e auditoria;
- centros e rateio: CRUD, validações negativas, regras percentual/fixa, estimativa, ausência de regra e proteção de rotas.

## Antes de deploy ou release local

Execute `python -m scripts.run_quality_checks`. O comando para na primeira falha e agrega AST, import, templates, Alembic, banco, auditorias existentes e pytest.

## Limitacoes

- os testes de integracao dependem de PostgreSQL acessivel;
- ainda nao ha medicao percentual de cobertura de linhas;
- permanecem avisos de depreciacao do `FastAPI.on_event`, sem impacto funcional atual;
- o runner completo e mais demorado porque executa auditorias amplas de seguranca e persistencia.
