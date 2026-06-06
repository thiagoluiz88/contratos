# Auditoria de persistência PostgreSQL

Data da auditoria: 06/06/2026

## Resumo

- O sistema usa PostgreSQL por meio de SQLAlchemy e `DATABASE_URL` montada a partir do `.env`.
- Não há uso ativo de SQLite. O arquivo legado `contracts.db` está ignorado pelo Git.
- Todas as rotas mutáveis atuais usam `db.commit()` e possuem `db.rollback()` para falhas de banco.
- Não existem rotas HTTP `PUT`, `PATCH` ou `DELETE`; exclusões expostas pela interface usam `POST`.
- O startup não executa mais `Base.metadata.create_all()`. O schema deve ser atualizado pelo Alembic.
- Arquivos enviados são guardados no filesystem local; seus metadados e textos extraídos ficam no PostgreSQL.

## Persistência por módulo

| Módulo | Situação |
|---|---|
| Usuários | Criação, edição, desativação, promoção e reset de senha persistem em `users` e geram auditoria. |
| Perfis | Criação, edição e desativação persistem em `access_profiles` e geram auditoria. |
| Contratos | Importação, edição, cadastro adicional, eventos e exclusão persistem no PostgreSQL. |
| Upload de contratos | Cria `operators`, `import_batches`, `contracts`, `contract_files`, análise e auditoria em uma transação. |
| Análise do contrato | Upload e reprocessamento persistem em `ai_analyses`, `contract_issues` e `negotiation_opportunities`. |
| Comparação de contratos | Agora cria `contract_comparisons` e `contract_comparison_items`, incluindo resultado JSON. |
| Aditivos | Upload cria `contract_additives`, `contract_files`, `import_batches` e auditoria. |
| Auditoria | Eventos importantes persistem em `auth_audit_events`; a tela de auditoria é somente leitura. |
| Troca de senha | Persiste o hash bcrypt e registra evento de auditoria. |
| Reset de senha | Persiste o hash bcrypt e registra evento de auditoria. |
| Importação de arquivos | Lotes e arquivos persistem; o modelo `ImportedContractRecord` ainda não é usado pelo fluxo atual. |

## Rotas mutáveis auditadas

Todas recebem dados, alteram objetos SQLAlchemy, executam commit e retornam resposta ou redirecionamento:

- `POST /login`, `/register`, `/change-password`
- `POST /users/new`, `/users/{id}/edit`, `/users/{id}/deactivate`, `/users/{id}/make-admin`, `/users/{id}/reset-password`
- `POST /access-profiles/new`, `/access-profiles/{id}/edit`, `/access-profiles/{id}/deactivate`
- `POST /contracts/import`, `/contracts/{id}/additional`, `/contracts/{id}/edit`, `/contracts/{id}/events`, `/contracts/{id}/delete`
- `POST /analises-ia/upload`, `/analises-ia/run`
- `POST /comparacoes`

`db.refresh()` é usado quando o identificador ou os valores gerados pelo banco são necessários na resposta.

## Dados estáticos ou ainda sem gravação

- `upload.html`, `alerts.html`, `comparison.html` e `compare_builder.html` são templates legados sem rota ativa.
- `comparacoes.js` é um JavaScript legado e não é mais carregado pela tela atual.
- As opções de índice de reajuste, critérios de comparação e instruções de análise são configurações estáticas, não cadastros.
- Dashboard, rankings e indicadores são calculados em memória a partir de dados reais do PostgreSQL; não precisam ser persistidos.
- Os modelos `ContractAdjustment`, `RemunerationTable`, `RemunerationTableItem`, `MaterialsMedicinesRule`, `NegotiationMessage`, `ImportedContractRecord` e `ContractClause` não possuem telas/rotas completas de cadastro atualmente.
- Aditivos possuem criação por upload, mas ainda não possuem ações de edição ou exclusão.
- Comparações possuem criação e listagem, mas ainda não possuem ações de edição ou exclusão.

## Ajustes realizados

- Adicionadas rotas reais para visualizar, editar e excluir contratos e criar eventos.
- Alterado o botão de exclusão de contrato de link GET para formulário POST.
- Reprocessamento de análise agora cria uma nova análise persistida.
- Comparações agora são criadas e listadas a partir do PostgreSQL.
- Datas de comparação agora são convertidas para JSON antes da persistência.
- Adicionados rollbacks ausentes nas rotas administrativas.
- Adicionada auditoria ao cadastro adicional e às novas ações importantes.
- Removido `create_all()` automático do startup.
- Corrigido `db_checks` para não deixar tabela técnica no banco.
- Criado teste integrado reproduzível em `scripts/audit_persistence.py`.

## Testes executados

Comandos:

```powershell
.\.venv\Scripts\python.exe -m app.db_checks
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m scripts.audit_persistence
```

Resultados:

- Conexão, INSERT, UPDATE e DELETE no PostgreSQL: OK.
- Schema alinhado ao Alembic: OK.
- Cadastro/edição/desativação de usuário e reset/troca de senha: OK.
- Cadastro/edição/desativação de perfil: OK.
- Upload, edição, cadastro adicional, evento e exclusão de contrato: OK.
- Análise, aditivo e comparação: OK.
- Nova inicialização da aplicação seguida de consulta em nova sessão: todos os registros esperados continuaram salvos.
