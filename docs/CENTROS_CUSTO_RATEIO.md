# Centros de Custo e Rateio

## Objetivo

Preparar estimativas rastreaveis de custo indireto sem alterar a producao importada e sem afirmar margem real.

Custos diretos pertencem ao atendimento/item e podem vir em `production_records.cost_value`. Custos indiretos representam estruturas compartilhadas e precisam de regra explicita, centro responsavel, vigencia e metodo.

## Metodos

- `percentual`: aplica o percentual sobre custo direto; se ausente, usa valor pago e informa a base;
- `valor_fixo`: adiciona valor fixo por registro aplicavel;
- `por_quantidade`: multiplica o valor configurado pela quantidade;
- `manual_futuro`: registra a intencao, mas retorna pendencia.

Regras podem filtrar categoria e item e so se aplicam dentro da vigencia, quando regra e centro estao ativos. Percentuais e valores negativos sao bloqueados.

## Uso

Cadastre centros em `/cost-centers` e regras em `/cost-allocation-rules`. Na producao consolidada, abra o item para consultar `/production/records/{id}/cost-estimate`.

A consulta nao grava custo estimado em `production_records`. O resultado sempre exibe: `Estimativa preliminar. Não representa margem final.`

## Limitacoes

- sem base contabil ou centro oficial importado;
- sem rateio por periodo, leito, hora, metro quadrado ou direcionador composto;
- regras concorrentes sao somadas e precisam de revisao humana;
- percentual usa custo direto e, na ausencia, valor pago;
- nenhuma margem final e calculada.

## Testes

`python -m pytest tests/test_cost_allocation.py`

