# Modulo 2 - Simulacao e Defasagem

## Objetivo

Permitir que a equipe simule uma nova tabela contratual antes de gravar dados definitivos em `contract_terms`.

## Estados da simulacao

- `simulada`: proposta criada e comparavel;
- `aprovada`: revisao humana liberou aplicacao;
- `aplicada`: proposta virou nova versao oficial;
- `cancelada`: proposta descartada;
- `erro`: falha controlada durante aplicacao.

## Regras de seguranca

- Simulacao nao altera tabela oficial.
- Aplicacao exige simulacao aprovada.
- Aplicacao duplicada e bloqueada.
- Versoes antigas nao sao apagadas.
- Nao ha chamada de API externa.
- Nao ha dados ficticios de mercado.

## Rotas

- `GET /contracts/{id}/terms/simulations`
- `GET /contracts/{id}/terms/simulations/new`
- `POST /contracts/{id}/terms/simulations`
- `GET /contracts/{id}/terms/simulations/{simulation_id}`
- `POST /contracts/{id}/terms/simulations/{simulation_id}/approve`
- `POST /contracts/{id}/terms/simulations/{simulation_id}/apply`
- `POST /contracts/{id}/terms/simulations/{simulation_id}/cancel`
- `POST /documents/{id}/create-table-simulation`
- `GET /reference-tables`
- `POST /reference-tables`
- `POST /reference-tables/{id}/items`
- `GET /contracts/{id}/terms/reference-compare`

## Referencia e defasagem

Tabelas de referencia sao cadastradas manualmente. A comparacao inicial usa categoria, item e unidade para localizar correspondencia. Sem referencia ativa, a tela informa que nao ha base para calcular.

O calculo de defasagem comercial ainda e preparatorio. A etapa futura deve considerar volume assistencial, codigos padronizados, tabelas licenciadas ou referencias internas validadas.

## Como testar

1. Abra um contrato com tabela vigente.
2. Acesse `/contracts/{id}/terms/simulations/new`.
3. Cadastre itens com valor proposto.
4. Abra a simulacao e confira novos, removidos, aumentos e reducoes.
5. Tente aplicar antes de aprovar e confirme bloqueio.
6. Aprove a simulacao.
7. Aplique como nova versao oficial.
8. Confira `/contracts/{id}/terms` e o historico.
9. Cadastre uma referencia vazia/manual em `/reference-tables`.
10. Compare em `/contracts/{id}/terms/reference-compare`.
