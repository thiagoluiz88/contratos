# Modulo 2 - Auto-Cadastro e Gestao de Tabelas

## Objetivo

O Modulo 2 organiza as condicoes aprovadas em `contract_terms` como tabelas contratuais versionadas. Ele permite ver a tabela vigente, historico de versoes e comparacao entre uma versao anterior e uma nova versao criada por contrato, aditivo ou revisao aprovada.

## Versionamento

Cada linha de `contract_terms` possui:

- contrato;
- categoria;
- item;
- unidade;
- valor de referencia;
- versao;
- vigencia inicial/final;
- indicador de versao vigente;
- documento de origem;
- usuario criador, quando disponivel.

Versoes antigas nao sao apagadas. Quando uma nova tabela e aplicada, as linhas vigentes anteriores sao encerradas e a nova versao passa a ser marcada como atual.

## Comparacao de versoes

A rota `/contracts/{id}/terms/compare?from_version=1&to_version=2` compara duas versoes e classifica cada item como:

- sem_alteracao;
- novo;
- removido;
- aumento;
- reducao;
- alteracao_descricao;
- alteracao_unidade;
- alteracao_vigencia.

O pareamento usa regras deterministicas:

1. mesma categoria + item + unidade;
2. item semelhante dentro da mesma categoria;
3. sem correspondencia vira novo ou removido.

Nao ha IA nesta etapa.

## Resumo financeiro

A tela mostra contagem de itens, novos/removidos, aumentos/reducoes e maiores variacoes percentuais. O impacto financeiro assistencial ainda nao e calculado porque depende de volume de uso.

## Relacao com aditivos

Quando uma versao vem de documento/aditivo, a tela exibe o documento de origem. Aditivos vinculados ao contrato aparecem na tela de tabelas para consulta rapida.

## Exportacao

A comparacao pode ser exportada em CSV por:

`/contracts/{id}/terms/compare/export?from_version=1&to_version=2`

## Simulacao antes da aplicacao oficial

A rota `/contracts/{id}/terms/simulations` permite criar uma tabela simulada sem alterar `contract_terms`.

Fluxo:

1. criar simulacao manual ou a partir de extracao aprovada;
2. comparar tabela vigente x tabela simulada;
3. revisar diferencas;
4. aprovar a simulacao;
5. aplicar como nova versao oficial somente por acao humana.

Aplicar uma simulacao aprovada encerra a versao vigente, preserva as linhas antigas e cria nova versao em `contract_terms`. Simulacoes nao aprovadas, canceladas ou ja aplicadas sao bloqueadas.

## Tabelas de referencia

A rota `/reference-tables` permite cadastrar uma tabela de referencia vazia/manual. O sistema nao cria CBHPM, tabela de mercado ou valores ficticios. A comparacao em `/contracts/{id}/terms/reference-compare` usa apenas referencias cadastradas pelo usuario.

Quando nao existe tabela ativa, a tela informa claramente que nao ha referencia disponivel.

## Defasagem futura

O servico `reference_table_comparison_service.py` prepara funcoes para comparar valores contratuais vigentes com uma tabela de referencia cadastrada. O calculo ainda e controlado e depende de dados reais informados pelo usuario.

## Limitacoes atuais

- Nao calcula impacto financeiro assistencial sem volume.
- Nao importa CBHPM automaticamente.
- Nao usa IA para pareamento de itens.
- A referencia so compara chaves normalizadas simples: categoria + item + unidade.
- Simulacoes exigem aprovacao antes de aplicar ao cadastro oficial.

## Proxima etapa

Evoluir para BI Comercial, com defasagem por operadora, impacto por volume assistencial, priorizacao de renegociacao e comparacao contra referencias reais licenciadas ou internas.
