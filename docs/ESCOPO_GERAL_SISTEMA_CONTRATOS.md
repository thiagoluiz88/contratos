# Escopo Geral do Sistema de Contratos Hospitalares

## Objetivo geral

O sistema de Gestão de Contratos Hospitalares deve ser tratado como uma plataforma de inteligência contratual hospitalar, e não apenas como um cadastro simples de contratos.

Seu objetivo é centralizar, organizar, analisar e apoiar a tomada de decisão sobre contratos com operadoras e convênios, reunindo documentos originais, aditivos, tabelas comerciais, regras contratuais, prazos, reajustes, alertas, auditoria, validação humana e indicadores comerciais.

A plataforma deve apoiar o Hospital São Francisco de Assis na gestão profissional dos contratos, com foco em:

- Redução de riscos financeiros e jurídicos.
- Controle de vigências, reajustes e aditivos.
- Preservação do histórico contratual.
- Comparação entre operadoras.
- Apoio à negociação com base em dados reais.
- Preparação para integração futura com ERP hospitalar.

O projeto deve aproveitar a estrutura atual, manter PostgreSQL, preservar autenticação, perfis, auditoria e evoluir de forma incremental.

## Módulos oficiais

### 1. Motor de Inteligência Artificial e Extração

O sistema deve permitir upload de contratos originais e aditivos em PDF, Word ou imagem, com suporte a OCR para documentos digitalizados.

O motor de IA ou extração deve buscar, quando tecnicamente possível:

- Valores de diárias.
- Taxas.
- Pacotes.
- Materiais.
- Medicamentos.
- OPME.
- Honorários médicos.
- Cláusulas críticas.
- Prazos de faturamento.
- Regras de glosa.
- Regras de auditoria.
- Multas.
- Vigência.
- Data-base.
- Índice de reajuste.

Os dados extraídos devem ser convertidos para uma estrutura organizada, preferencialmente JSON ou modelo equivalente, para posterior validação humana e gravação definitiva.

Enquanto não houver integração real com IA externa, o sistema não deve inventar resultados. Toda extração automática deve ser apresentada como dado preliminar, pendente de validação.

### 2. Auto-Cadastro e Gestão de Tabelas

O sistema deve usar os dados extraídos para pré-preencher tabelas contratuais e condições comerciais.

Deve existir um fluxo de validação humana em que o usuário veja:

- Documento original de um lado.
- Dados extraídos do outro.
- Campos editáveis para correção.
- Botão de aprovação para gravar as informações no banco.

O sistema deve tratar aditivos de forma inteligente. Ao aprovar um aditivo que altere valores, regras ou vigências, a tabela anterior deve ter sua vigência encerrada e uma nova versão deve ser criada, preservando o histórico.

A gestão de tabelas deve permitir versionamento e cálculo de defasagem em relação a tabelas de referência, como CBHPM ou outra tabela padrão configurada pelo hospital.

### 3. Gestão de Contratos e Relacionamento

O contrato principal deve ser tratado como documento mãe. Aditivos devem ser tratados como documentos filhos, vinculados ao contrato principal.

A ficha da operadora deve conter, no mínimo:

- Razão social.
- Nome da operadora.
- CNPJ.
- Registro ANS.
- Status.
- Observações.
- Contatos principais.

O painel de contatos da operadora deve registrar:

- Nome.
- Cargo.
- E-mail.
- Telefone.

O sistema deve manter um repositório digital seguro dos documentos originais, incluindo contratos, aditivos e documentos de apoio.

### 4. Business Intelligence e Inteligência Comercial

O sistema deve oferecer recursos de BI comercial para apoiar diretoria, contratos e financeiro.

Indicadores e análises esperadas:

- Ranking de rentabilidade por operadora.
- Comparação lado a lado entre operadoras.
- Comparação de valores de diárias.
- Comparação de taxas.
- Comparação de pacotes.
- Comparação de índices e datas-base.
- Identificação das melhores condições comerciais.
- Identificação das piores condições comerciais.
- Apoio à negociação com base em dados cadastrados e validados.

O BI deve usar dados reais persistidos no banco. Não devem ser usados dados mockados em produção.

### 5. Automação de Prazos e Notificações

O sistema deve controlar prazos contratuais e gerar alertas operacionais.

Alertas mínimos:

- Vencimento contratual com 60 dias de antecedência.
- Vencimento contratual com 30 dias de antecedência.
- Vencimento contratual com 15 dias de antecedência.
- Data-base de reajuste.
- Documentação pendente.
- Validação humana pendente.

O sistema deve possuir uma central de alertas no painel principal.

Em evolução futura, poderá enviar e-mails para gestores responsáveis. Nenhuma integração externa deve ser criada sem necessidade imediata, mas a estrutura deve permanecer limpa para essa expansão.

Todo alerta gerado e visualizado deve ser registrado para rastreabilidade.

### 6. Segurança, Integração e Auditoria

O sistema deve manter trilha de auditoria completa para ações relevantes.

Eventos mínimos auditáveis:

- Login.
- Logout.
- Upload de documento.
- Extração automática.
- Aprovação humana.
- Alteração manual.
- Criação de contrato.
- Criação de aditivo.
- Alteração de tabela.
- Inativação.
- Exclusão, quando existir.
- Exportação de dados.
- Alteração de perfil de usuário.

O controle de acesso deve ser feito por perfil.

Perfis mínimos oficiais:

- Administrador.
- Diretoria.
- Contratos.
- Financeiro.
- Auditoria.
- Somente leitura.

O sistema deve ser preparado para exportação ou API futura para ERP hospitalar, como Tasy, MV, Philips ou outro sistema usado pelo hospital. Essa preparação deve ser documentada e incremental. Nenhuma integração externa deve ser criada agora sem necessidade.

## Fluxo ideal do contrato

1. Usuário autenticado realiza upload do contrato original.
2. Sistema armazena o documento em repositório seguro.
3. Motor de extração lê o documento e identifica dados relevantes.
4. Sistema gera uma estrutura preliminar com dados cadastrais, financeiros, jurídicos e operacionais.
5. Usuário validador revisa os dados extraídos.
6. Usuário corrige informações quando necessário.
7. Usuário aprova a gravação.
8. Sistema cria ou atualiza o contrato principal.
9. Sistema grava tabelas, condições, prazos, reajustes e regras associadas.
10. Sistema registra auditoria da aprovação.
11. Dashboard e BI passam a considerar o contrato como dado validado.
12. Alertas de vigência, reajuste e documentação passam a ser monitorados.

## Fluxo ideal do aditivo

1. Usuário realiza upload do aditivo.
2. Sistema identifica o contrato principal relacionado.
3. Sistema armazena o documento como filho do contrato principal.
4. Motor de extração identifica alterações de valores, prazos, regras, índices ou vigência.
5. Usuário valida os dados extraídos.
6. Se o aditivo alterar tabela ou condição vigente, o sistema encerra a versão anterior.
7. Sistema cria nova versão da tabela ou condição contratual.
8. Sistema preserva o histórico anterior.
9. Sistema registra auditoria da aprovação.
10. Dashboard, alertas e BI passam a considerar a versão vigente.

## Papel da IA

A IA deve apoiar leitura, triagem e extração de informações contratuais.

Ela pode:

- Sugerir campos pré-preenchidos.
- Resumir contratos.
- Identificar cláusulas críticas.
- Apontar riscos financeiros.
- Apontar riscos jurídicos.
- Detectar ausência de reajuste.
- Sugerir pontos para negociação.
- Comparar contratos ou aditivos.

A IA não substitui validação humana. Nenhuma informação extraída deve ser tratada como definitiva sem aprovação.

Caso a IA não esteja integrada, o sistema deve deixar o fluxo preparado, com status claro de pendente, extraído, validado ou rejeitado.

## Papel da validação humana

A validação humana é etapa obrigatória para transformar dados extraídos em dados oficiais.

O usuário validador deve:

- Conferir o documento original.
- Confirmar campos extraídos.
- Corrigir dados incorretos.
- Rejeitar extrações sem base documental.
- Aprovar gravação no banco.

Somente dados validados devem alimentar indicadores oficiais, comparações comerciais, alertas críticos e integrações futuras.

## Papel do BI

O BI deve transformar contratos e tabelas em informação gerencial.

Ele deve apoiar:

- Diretoria na visão estratégica.
- Financeiro na análise de rentabilidade.
- Equipe de contratos na priorização de renegociações.
- Auditoria na identificação de riscos e inconsistências.

O BI deve comparar operadoras, vigências, reajustes, regras de glosa, prazos de pagamento, tabelas comerciais e condições relevantes.

Seu objetivo é apoiar negociação baseada em evidências, não apenas armazenar documentos.

## Papel da auditoria

A auditoria deve garantir rastreabilidade, segurança e responsabilidade.

Toda ação relevante deve registrar:

- Usuário.
- Data e hora.
- Ação executada.
- Entidade afetada.
- Resultado.
- Detalhes necessários para reconstrução do evento.

A auditoria deve cobrir o ciclo de vida completo do contrato, desde upload até inativação, exportação ou integração futura.

## Visão futura de integração com ERP

O sistema deve ser preparado para integração futura com ERP hospitalar, como Tasy, MV, Philips ou outro sistema utilizado pelo hospital.

Possibilidades futuras:

- Exportação de tabelas validadas.
- Consulta de contratos vigentes por operadora.
- Envio de condições comerciais aprovadas.
- Integração de códigos de procedimentos, materiais, medicamentos e pacotes.
- Sincronização de operadoras e dados cadastrais.
- Apoio a faturamento, auditoria de contas e negociação comercial.

Essa integração deve ser feita de forma controlada, documentada e segura. No momento, o foco é preparar a base interna, garantir dados confiáveis, manter histórico e evitar dependência prematura de sistemas externos.

## Regras permanentes de desenvolvimento

- Aproveitar a estrutura atual do projeto.
- Não recriar o sistema do zero.
- Não apagar funcionalidades sem justificativa.
- Não usar dados mockados em produção.
- Não inventar extrações falsas de IA.
- Manter PostgreSQL como banco principal.
- Criar migrations corretamente.
- Manter autenticação, perfis e auditoria.
- Usar interface em português do Brasil.
- Priorizar uso real hospitalar.
- Separar dado extraído, dado validado e dado oficial.
- Preservar histórico de contratos, aditivos e tabelas.
- Preparar integrações futuras sem implementá-las antes da necessidade.
## Modulo 2 - Gestao de tabelas contratuais

O sistema passa a contar com uma visao versionada de `contract_terms`, permitindo consultar a tabela vigente de cada contrato, historico de versoes, origem documental e comparacao entre versoes.

Principais rotas:

- `/contracts/{id}/terms`
- `/contracts/{id}/terms/compare`
- `/contracts/{id}/terms/compare/export`

A comparacao identifica itens sem alteracao, novos, removidos, aumentos, reducoes e alteracoes de descricao, unidade ou vigencia. A etapa futura sera comparar contra tabela de referencia e calcular defasagem comercial.

## Modulo 2 - Simulacao e referencia

O sistema passa a permitir simulacao de uma nova tabela contratual antes da aplicacao oficial. A simulacao e separada de `contract_terms`, pode ser revisada, comparada e aprovada, e somente depois de acao humana pode virar uma nova versao oficial.

Tambem foi criada uma base para tabelas de referencia manuais. O sistema nao cria CBHPM nem valores de mercado automaticamente; a referencia depende de dados reais cadastrados pelo usuario. A proxima etapa sera usar essas referencias para BI Comercial e calculo de defasagem por operadora.
# Modulo 4 - BI Comercial

A primeira versao funcional consolida contratos e condicoes oficiais vigentes em indicadores conservadores, ranking por Score Comercial, melhores/piores condicoes, alertas cadastrais, comparativo executivo e CSV. Rentabilidade real permanece fora do escopo ate a integracao de volume assistencial e custos. Consulte `docs/MODULO_4_BI_COMERCIAL.md`.
