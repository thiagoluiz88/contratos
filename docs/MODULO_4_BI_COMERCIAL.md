# Modulo 4 - BI Comercial

## Objetivo

Oferecer uma leitura executiva, conservadora e auditavel das condicoes comerciais cadastradas no sistema, sem transformar valores nominais de contrato em margem ou rentabilidade presumida.

> Rentabilidade real depende de producao/volume assistencial e custos.

> Nesta versao, o ranking sera baseado em condicoes contratuais cadastradas e comparacoes referenciais, nao em margem real.

## Dados de origem

- operadoras ativas e seus dados cadastrais;
- contratos ativos e seus vinculos com operadoras;
- somente `contract_terms` oficiais com `is_current=true` no ranking atual;
- simulacoes pendentes ou aprovadas apenas como indicador de processo;
- tabelas e itens de referencia ativos, quando cadastrados;
- datas contratuais e origem documental dos termos;
- `audit_logs` para acessos, comparacoes e exportacoes.

Versoes antigas continuam preservadas pelo Modulo 2, mas nao entram no ranking principal.

## Indicadores da primeira versao

- total de operadoras e contratos ativos;
- contratos com e sem tabela vigente;
- itens contratuais vigentes;
- contratos com e sem correspondencia em referencia ativa;
- simulacoes ainda pendentes de aplicacao;
- Score Comercial por operadora;
- medias nominais por categoria;
- maiores e menores condicoes por categoria;
- comparativo executivo entre 2 e 10 contratos;
- alertas de completude e qualidade cadastral.

## Score Comercial

O score varia de 0 a 100 e combina componentes transparentes:

- ate 30 pontos pela quantidade de itens vigentes;
- ate 30 pontos pela diversidade de categorias;
- ate 20 pontos pela presenca de diaria, taxa, pacote, OPME e honorario;
- ate 20 pontos pela cobertura de itens em tabela de referencia.

O score mede completude e comparabilidade contratual. Valores altos nao significam, por si so, maior margem, menor custo ou melhor rentabilidade.

## Referencias e defasagem

Quando existe tabela ativa, o BI reutiliza `reference_table_comparison_service.py` e apresenta itens acima, abaixo, iguais e sem referencia. Sem tabela ativa, informa claramente: `Sem tabela de referência cadastrada.` Nenhum valor e criado para preencher ausencias.

## Indicadores que dependem de volume assistencial

- impacto financeiro mensal ou anual;
- receita estimada por operadora;
- ganho ou perda por mudanca de tabela;
- peso de cada item na producao;
- rentabilidade e margem reais;
- simulacao financeira de negociacao.

## Alertas

- contrato ativo sem tabela vigente;
- poucas condicoes vigentes;
- ausencia de data-base;
- vencimento em ate 90 dias sem simulacao pendente;
- operadora sem CNPJ;
- contrato sem operadora vinculada;
- condicao vigente sem origem identificavel.

## Rotas e exportacoes

- `GET /bi/commercial`
- `GET /bi/commercial/operators`
- `GET /bi/commercial/compare?contract_ids=1,2,3`
- `GET /bi/commercial/export/ranking`
- `GET /bi/commercial/export/conditions`
- `GET /bi/commercial/compare/export?contract_ids=1,2,3`

Administrador, Diretoria, Contratos, Financeiro, Auditoria e Somente leitura podem visualizar. O perfil Somente leitura nao exporta CSV.

## Limitacoes atuais

- nao existe producao ou volume assistencial no calculo;
- custos hospitalares nao estao integrados;
- valores de categorias distintas nao sao diretamente equivalentes;
- correspondencia referencial depende de categoria, item e unidade consistentes;
- a primeira tabela de referencia ativa e usada no resumo contratual;
- nao existe ponderacao por frequencia de uso;
- nao ha IA nem fonte externa nesta versao.

## Como testar

```powershell
python -m pytest tests/test_commercial_bi.py
python -m scripts.run_quality_checks
```

## Proximos passos

Importar producao/volume assistencial e custos por item, com rastreabilidade de origem, para estimar impacto financeiro real e cenarios de negociacao por operadora.

## Base de producao e custos

O sistema agora possui lotes e registros rastreaveis de producao. O BI exibe apenas totais importados e alertas de completude; o Score Comercial permanece exclusivamente contratual. Consulte `docs/MODULO_4_PRODUCAO_CUSTOS.md`.

A precificacao financeira preparada usa a versao contratual vigente na data do atendimento. Essa evolucao nao altera o Score Comercial nem publica ranking de rentabilidade.
