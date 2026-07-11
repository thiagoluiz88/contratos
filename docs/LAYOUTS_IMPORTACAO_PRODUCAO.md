# Layouts de Importacao de Producao

## Finalidade

Layouts permitem mapear colunas reais de CSV ou Excel para os campos internos sem declarar nenhum formato de Tasy, MV ou Philips como oficial. Cada layout registra sistema, tipo, delimitador, encoding, status, autor e mapeamentos.

## Campos alvo

Obrigatorios para ativar um layout: `operadora`, `contrato`, `competencia`, `data_atendimento`, `categoria`, `item`, `descricao`, `quantidade`, `unidade`, `valor_faturado`, `valor_pago`, `valor_glosado` e `custo`.

Opcionais: `guia`, `conta`, `atendimento` e `paciente_referencia`.

Cada mapeamento possui coluna de origem, valor padrao e transformacao opcional (`strip`, `upper`, `lower` ou `digits`).

## Criacao e uso

1. Acesse `/production/layouts/new`.
2. Cadastre como `rascunho` enquanto os campos obrigatorios estiverem incompletos.
3. Mapeie os nomes exatos recebidos da fonte.
4. Ative o layout depois da validacao.
5. Em `/production/imports/new`, selecione o layout e envie arquivo do mesmo tipo.

Sem layout selecionado, permanecem os aliases padrao da importacao original. Nenhum alias foi removido.

## CSV e Excel

CSV aceita delimitador e encoding configurados. Sem configuracao, tenta reconhecer ponto e virgula, virgula ou tabulacao e UTF-8/Latin-1.

Excel aceita apenas `.xlsx` por `openpyxl`, usa a primeira aba e exige cabecalho. `.xls` legado e bloqueado. Multiplas abas e selecao de planilha ficam para etapa futura.

## Rastreabilidade

O lote registra `layout_id` e resumo com layout usado, colunas reconhecidas, ignoradas e obrigatorias ausentes. O arquivo original permanece associado ao lote. Audit logs nao recebem linhas completas.

## Preview

Use `/production/imports/preview` antes da importacao definitiva. O arquivo fica apenas em diretorio temporario durante a requisicao, e removido no `finally`, e no maximo 50 linhas sao analisadas. O preview mostra abas, colunas detectadas/reconhecidas/ignoradas, obrigatorias ausentes, validacoes e dados normalizados. Nao cria lote nem `production_records` e mascara a referencia de paciente como hash.

## Precificacao historica

A receita esperada procura a versao de `contract_terms` cuja vigencia contenha a data do atendimento. Em seguida combina categoria, item e unidade. Sem contrato, data, quantidade, versao ou item correspondente, retorna pendencia e nao usa o preco atual como fallback.

## Custos indiretos

`cost_centers` e `cost_allocation_rules` nao foram criados. Antes disso, precisam ser definidos centros oficiais, metodos de rateio, vigencias, bases de alocacao e responsaveis. Nenhum rateio real e calculado atualmente.
