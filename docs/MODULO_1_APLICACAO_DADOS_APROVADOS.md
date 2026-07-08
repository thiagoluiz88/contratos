# Modulo 1 - Aplicacao de dados aprovados

## Conceitos

- Candidato: sugestao gerada pela analise interpretativa local.
- Aprovado: usuario revisou e aprovou o JSON final da extracao.
- Aplicado: dados aprovados foram gravados no cadastro definitivo.

A aprovacao nao altera o cadastro. A aplicacao e uma acao separada, feita por `POST /documents/{id}/apply`.

## Operadora

A aplicacao tenta localizar operadora por CNPJ. Se nao houver CNPJ, tenta localizar por nome exato normalizado. Operadoras novas so sao criadas quando ha nome e algum dado complementar seguro, como CNPJ ou razao social.

Campos existentes nao sao sobrescritos automaticamente. Divergencias entram em `apply_summary.campos_ignorados`.

## Contrato

Quando o documento ja esta vinculado a um contrato, a aplicacao atualiza esse contrato. Campos preenchidos sao preservados; somente campos vazios recebem dados aprovados.

Campos tratados:

- operadora
- numero do contrato
- tipo
- assinatura
- inicio/fim de vigencia
- data-base
- indice e percentual de reajuste

## Aditivos

Documentos do tipo `aditivo` criam ou localizam um registro em `contract_additives`, vinculado ao contrato principal do documento. O contrato mae nao e alterado de forma destrutiva.

## Condicoes contratuais

Condicoes aprovadas sao gravadas em `contract_terms`.

Regras:

- versoes antigas nao sao apagadas;
- termos atuais sao encerrados com `is_current=false`;
- nova versao recebe `version = max(version) + 1`;
- linhas sem item/descricao ou sem valor aprovado viram pendencia;
- `source_document_id` aponta para o documento aplicado.

## Permissoes

Podem aplicar dados aprovados:

- Administrador
- Contratos
- Diretoria

Auditoria e Somente leitura nao aplicam dados ao cadastro.

## Auditoria

Sao registrados eventos para inicio, bloqueios, operadora criada/atualizada, contrato atualizado/criado, aditivo criado/vinculado, versoes encerradas, novas condicoes, conclusao, pendencias e erro.

## Como testar

1. Enviar documento.
2. Gerar candidatos.
3. Salvar revisao.
4. Aprovar.
5. Clicar em `Aplicar ao cadastro`.
6. Conferir documento, contrato, operadora, `contract_terms` e auditoria.

## Limitacoes

- Nao sobrescreve campos preenchidos automaticamente.
- Criacao de contrato sem vinculo exige dados minimos.
- Comparacao visual entre tabela anterior e nova tabela fica para o Modulo 2.
