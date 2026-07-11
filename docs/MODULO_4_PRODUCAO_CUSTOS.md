# Modulo 4 - Producao Assistencial e Custos

## Objetivo

Criar uma base rastreavel para importar producao assistencial, valores faturados, pagos, glosados e custos. O modulo prepara calculos financeiros futuros sem alterar contratos ou tabelas oficiais.

> Sem producao assistencial e custos, o sistema nao deve afirmar rentabilidade real.

## BI contratual x BI financeiro

O BI Comercial atual mede completude e comparabilidade de condicoes vigentes. Ele nao conhece frequencia de uso, valor efetivamente pago nem custo hospitalar. O BI financeiro futuro precisara combinar:

- quantidade realizada por item;
- valor contratual oficial vigente na data/competencia;
- valor faturado e efetivamente pago;
- glosas;
- custo assistencial e operacional rastreavel;
- regras de rateio e centros de custo, quando aplicaveis.

Nesta etapa, `financial_impact_service.py` oferece apenas estimativas basicas e sempre retorna insuficiencia quando volume, correspondencia ou custo estao ausentes.

## Fontes esperadas

- exportacao CSV de ERP hospitalar;
- Tasy, MV ou Philips por arquivo, em etapa posterior;
- planilhas controladas;
- Excel, depois da definicao de dependencia e layout;
- API futura autenticada e auditada.

Nenhuma integracao externa foi criada nesta versao.

## Rastreabilidade

`production_import_batches` guarda origem, arquivo, sistema, usuario, datas, status e totais. `production_records` guarda a linha de origem, validacao e vinculos encontrados. Lotes processados nao podem ser reprocessados ou cancelados.

Linhas invalidas nao derrubam o lote: ficam com `validation_status=pendente` e mensagem objetiva. O audit log registra eventos, IDs e contagens, nunca a linha completa.

Referencias de paciente sao transformadas em SHA-256. Nao envie nome, CPF, prontuario ou outro dado pessoal desnecessario.

## Estrutura de custo

O campo `cost_value` permanece em `production_records` nesta primeira versao. Isso preserva a relacao direta entre quantidade, faturamento, pagamento, glosa e custo da mesma linha. Uma tabela `cost_records` separada sera avaliada quando existirem custos indiretos, centros de custo ou rateios independentes da producao.

## Layout CSV padrao

Cabeçalho recomendado:

```text
operadora;contrato;competencia;data_atendimento;categoria;item;descricao;quantidade;unidade;valor_faturado;valor_pago;valor_glosado;custo;guia;conta;atendimento;paciente_referencia
```

Colunas obrigatorias no arquivo:

- `operadora`, `contrato`, `competencia`, `data_atendimento`;
- `categoria`, `item`, `descricao`, `quantidade`, `unidade`;
- `valor_faturado`, `valor_pago`, `valor_glosado`, `custo`.

Os valores podem ficar vazios quando a fonte nao os possui; valores preenchidos precisam ser numericos. `guia`, `conta`, `atendimento` e `paciente_referencia` sao opcionais.

Formatos de data aceitos: `AAAA-MM-DD`, `DD/MM/AAAA`, `AAAA-MM` e `MM/AAAA` para competencia. Separadores CSV aceitos: ponto e virgula, virgula ou tabulacao.

## Vinculos

- operadora: CNPJ normalizado ou nome exato, sem diferenca de maiusculas;
- contrato: ID, numero ou nome, preferencialmente dentro da operadora localizada;
- vinculo ausente: registro permanece como pendencia, sem criacao automatica de operadora ou contrato.

## Telas e rotas

- `GET /production/imports`
- `GET /production/imports/new`
- `POST /production/imports`
- `GET /production/imports/{id}`
- `POST /production/imports/{id}/cancel`
- `GET /production/records`
- `GET /production/records/export`

Administrador, Diretoria, Contratos, Financeiro e Auditoria visualizam. Importacao e cancelamento ficam restritos a Administrador, Contratos e Financeiro.

## Calculos basicos preparados

- receita contratual estimada: quantidade valida x valor oficial vigente correspondente;
- impacto aritmetico de percentual de reajuste;
- comparacao ponderada entre tabela atual e simulada usando o mesmo volume;
- margem bruta estimada: valor pago menos custo, somente com ambos completos.

Esses resultados nao representam faturamento final, margem contabil ou rentabilidade final.

## Layouts configuraveis e Excel

Layouts persistidos mapeiam colunas reais para campos alvo, sem assumir formatos oficiais de ERP. CSV continua com fallback por aliases quando nenhum layout e selecionado. Arquivos `.xlsx` usam a primeira aba pelo mesmo mecanismo; `.xls` permanece bloqueado. Consulte `docs/LAYOUTS_IMPORTACAO_PRODUCAO.md`.

Cada lote registra layout, colunas reconhecidas, ignoradas e obrigatorias ausentes. O preview interativo analisa ate 50 linhas em arquivo temporario removido ao final, sem criar lote ou producao.

## Centros de custo e rateio

Centros e regras vigentes permitem estimar custo indireto por percentual, valor fixo ou quantidade. A estimativa e consultiva, nao altera `production_records` e nao representa margem final. Consulte `docs/CENTROS_CUSTO_RATEIO.md`.

## Precificacao historica

`contract_term_pricing_service.py` seleciona a versao cuja vigencia inclui a data do atendimento e procura categoria, item e unidade. A receita esperada nao usa mais automaticamente a tabela atual para atendimentos historicos. Ausencias retornam pendencia clara.

## Limitacoes

- CSV e Excel `.xlsx`; sem `.xls` legado;
- sem Tasy/MV/Philips ou API;
- sem rateio de custo indireto;
- sem tratamento de sobreposicoes complexas de vigencia alem da maior versao aplicavel;
- correspondencia por categoria, item e unidade;
- sem conciliacao com contas ou glosas posteriores;
- sem calculo de margem real no BI principal.
- sem centros de custo e rateio indireto; estrutura pendente de definicao funcional.

## Como testar

```powershell
python -m pytest tests/test_production_imports.py
python -m pytest tests/test_financial_impact_service.py
python -m scripts.run_quality_checks
```

## Proximos passos

Validar layouts reais do ERP, criar mapeamentos configuraveis, vincular a versao contratual vigente na data do atendimento e definir custos diretos/indiretos antes de publicar ranking financeiro real.
