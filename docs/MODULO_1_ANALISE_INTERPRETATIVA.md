# Modulo 1 - Analise interpretativa local

## Objetivo

A analise interpretativa transforma o `extracted_text` de um documento em candidatos estruturados para revisao humana. Ela nao aplica dados em `contracts`, `operators` ou `contract_terms`.

## Parser deterministico local

A primeira versao usa regras locais, expressoes regulares e contexto textual curto. Nenhuma API externa e chamada e nenhuma internet e exigida. O metodo registrado no JSON e `local_rules`.

## Texto extraido x candidatos interpretados

- Texto extraido: conteudo bruto obtido por PDF digital, DOCX ou OCR local.
- Candidatos interpretados: sugestoes com `value`, `confidence` e `evidence`.
- Dado aprovado: JSON final salvo somente depois da acao humana de salvar/aprovar.

## Campos analisados

O parser busca candidatos de operadora, razao social, CNPJ, registro ANS, numero do contrato, tipo do documento, datas de vigencia, data-base, indice de reajuste, percentual, prazos, glosa, autorizacao, multas, auditoria, OPME, materiais, medicamentos, pacotes, diarias, taxas, honorarios e valores financeiros.

## Validacao humana obrigatoria

Os candidatos podem estar incompletos ou ambigueis. Por isso:

- nao sobrescrevem contrato;
- nao criam `contract_terms`;
- nao marcam aprovacao automaticamente;
- sempre exibem evidencia quando houver;
- podem ser corrigidos manualmente na tela `/documents/{id}/validate`.

## Como testar

1. Envie um documento em `/documents`.
2. Abra `/documents/{id}/validate`.
3. Clique em `Gerar candidatos a partir do texto`.
4. Revise valores, confidence e evidence.
5. Salve a revisao ou aprove/rejeite.

## Limitacoes

- A analise e heuristica e conservadora.
- Textos muito grandes sao limitados para evitar travar a requisicao.
- Valores financeiros sem contexto sao mantidos como aviso ou baixa confianca.
- Documento sem `extracted_text` continua disponivel para revisao manual.

## Aplicacao dos dados aprovados

A etapa de aplicacao foi separada da aprovacao. Candidatos continuam sendo apenas sugestoes; dados aprovados so entram no cadastro definitivo quando um usuario autorizado aciona `Aplicar ao cadastro`.

Detalhes: `docs/MODULO_1_APLICACAO_DADOS_APROVADOS.md`.

## Proxima etapa

Evoluir o Modulo 2 com comparacao visual entre tabela anterior e nova tabela aprovada por aditivo.
