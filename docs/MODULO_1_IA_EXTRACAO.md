# Modulo 1 - Motor de IA e Extracao

## Objetivo

O Modulo 1 cria o fluxo funcional de ingestao de documentos contratuais e validacao humana, deixando a base pronta para OCR, parser de documentos e IA em etapa futura.

Nesta fase, nao ha IA externa integrada, nao ha chamada para servico pago e nao sao inventados valores extraidos. O sistema extrai texto bruto quando possivel, prepara um JSON estruturado vazio ou preenchido manualmente pelo usuario validador e mantem a aprovacao humana como etapa obrigatoria.

## Fluxo de upload

1. Usuario acessa `Documentos e Extracao`.
2. Seleciona o contrato vinculado.
3. Seleciona o tipo do documento:
   - contrato
   - aditivo
   - tabela
   - anexo
   - outro
4. Envia arquivo em formato permitido.
5. Sistema salva o arquivo com nome interno seguro.
6. Sistema cria registro em `contract_files`.
7. Sistema cria registro em `contract_extractions`.
8. Sistema tenta extrair texto bruto localmente.
9. Documento fica com status `aguardando_validacao`.

Formatos aceitos nesta fase:

- PDF
- DOC
- DOCX
- PNG
- JPG
- JPEG

## Extracao de texto bruto

O servico `app/services/document_processing_service.py` executa parsers locais, sem IA interpretativa:

- PDF: tenta extrair texto da camada digital com `pdfplumber`.
- PDF escaneado: tenta OCR local somente se Poppler/Tesseract estiverem disponiveis.
- DOCX: extrai paragrafos e tabelas basicas com `python-docx`.
- DOC: arquivo e salvo, mas a extracao automatica fica pendente de conversao para DOCX/PDF.
- PNG/JPG/JPEG: tenta OCR local com `pytesseract` quando Tesseract estiver instalado.

Se OCR local nao estiver configurado, o fluxo nao falha. O documento e salvo, a validacao humana continua disponivel e o sistema registra aviso claro.

## Status de processamento

Status esperados em `contract_files.processing_status`:

- `pendente`
- `em_processamento`
- `texto_extraido`
- `aguardando_validacao`
- `aprovado`
- `rejeitado`
- `erro`

Status esperados em `contract_extractions.review_status`:

- `pendente`
- `em_revisao`
- `aprovado`
- `rejeitado`

## Fluxo de validacao humana

A tela `/documents/{id}/validate` apresenta:

- Dados do documento original.
- Link para abrir o arquivo original.
- Previa do texto extraido.
- Avisos de parser/OCR.
- Formulario de dados estruturados.
- Campos de contrato.
- Campos de clausulas criticas.
- Campos de condicoes contratuais.
- Campo de notas da revisao.

Acoes disponiveis:

- Salvar revisao.
- Aprovar cadastro.
- Rejeitar extracao.
- Voltar.

A aprovacao nesta fase muda o status para aprovado, mas nao aplica automaticamente os dados ao cadastro do contrato nem cria versoes de tabelas. Hooks foram deixados preparados no servico para essa etapa futura.

## Estrutura dos dados extraidos

Os dados sao armazenados em `contract_extractions.extracted_json`:

```json
{
  "contrato": {
    "operadora": null,
    "numero_contrato": null,
    "tipo_contrato": null,
    "data_inicio": null,
    "data_fim": null,
    "data_base_reajuste": null,
    "indice_reajuste": null,
    "percentual_reajuste": null
  },
  "clausulas_criticas": {
    "prazo_faturamento": null,
    "prazo_recurso_glosa": null,
    "regras_glosa": null,
    "regras_autorizacao": null,
    "multas": null,
    "auditoria": null
  },
  "condicoes_contratuais": [
    {
      "categoria": null,
      "item": null,
      "descricao": null,
      "valor": null,
      "unidade": null,
      "vigencia_inicio": null,
      "vigencia_fim": null
    }
  ]
}
```

O texto bruto fica em:

- `contract_extractions.extracted_text`
- `contract_extractions.extracted_text_preview`
- `contract_extractions.extraction_method`
- `contract_extractions.extraction_warnings`
- `contract_extractions.page_count`
- `contract_extractions.character_count`

## Auditoria

Eventos registrados em `audit_logs`:

- `document_processing_started`
- `text_extraction_started`
- `text_extracted`
- `ocr_not_configured`
- `no_text_detected`
- `text_extraction_error`
- `document_uploaded`
- `document_sent_to_validation`
- `document_processing_error`
- `extraction_review_saved`
- `extracted_fields_updated`
- `extraction_approved`
- `extraction_rejected`
- `validation_opened`

## Limitacoes atuais

- Nao ha IA real integrada.
- OCR depende de Tesseract e, para PDF escaneado, tambem de Poppler no Windows/PATH.
- Nao ha extracao automatica definitiva.
- Dados estruturados precisam ser conferidos e preenchidos pelo usuario.
- Aprovacao nao aplica automaticamente dados em `contracts` ou `contract_terms`.

## Configuracao de OCR local

Para imagens e PDFs escaneados, instale e configure localmente:

- Tesseract OCR no Windows.
- Pacote de idioma portugues, se necessario.
- Poppler no PATH para converter paginas de PDF em imagem.

Sem essa configuracao, o sistema registra o aviso: `OCR local não configurado. Documento enviado, mas texto não extraído automaticamente.`

## Como testar

- PDF com texto digital: enviar em `/documents` e conferir metodo `pdf_text`.
- DOCX: enviar documento com paragrafos/tabela e conferir metodo `docx`.
- Imagem: enviar PNG/JPG; se OCR nao estiver configurado, deve aparecer aviso sem quebrar upload.
- Extensao invalida: enviar `.exe`; o sistema deve bloquear.
- Validacao: acessar `/documents/{id}/validate`, revisar campos, salvar, aprovar ou rejeitar.

## Integracao futura de IA/OCR

O servico `app/services/document_processing_service.py` foi preparado para futura substituicao ou expansao com:

- OCR.
- Parser de PDF.
- Parser de Word.
- IA local.
- IA externa.

Pontos preparados:

- `process_uploaded_document()`
- `empty_extraction_payload()`
- `apply_approved_extraction_to_contract()`
- `apply_extracted_terms_to_contract_terms()`

Quando IA/OCR for implementada, ela deve preencher `extracted_json` com dados preliminares e manter a validacao humana como etapa obrigatoria antes de qualquer aplicacao definitiva no cadastro.
## Analise interpretativa local

O modulo agora inclui a primeira versao do motor interpretativo local em `app/services/contract_ai_analysis_service.py`.

- A rota `POST /documents/{id}/analyze` gera candidatos a partir do `extracted_text`.
- O metodo e deterministico (`local_rules`) e nao usa API externa.
- O resultado e salvo em `contract_extractions.extracted_json` como candidatos com `value`, `confidence` e `evidence`.
- A tela `/documents/{id}/validate` mostra candidatos e permite correcao humana.
- A aprovacao continua manual e nao aplica dados automaticamente em `contracts` ou `contract_terms`.

Detalhes operacionais estao em `docs/MODULO_1_ANALISE_INTERPRETATIVA.md`.

## Aplicacao dos dados aprovados

A aprovacao humana e separada da aplicacao no cadastro. Depois de `review_status=aprovado`, usuarios autorizados podem executar `POST /documents/{id}/apply` para gravar dados aprovados em operadoras, contratos, aditivos e `contract_terms`.

Regras completas: `docs/MODULO_1_APLICACAO_DADOS_APROVADOS.md`.
