# Constituição do firmware-ml-classifier

## Core Principles

### I. Somente análise estática

O projeto classifica firmware sem executá-lo. Nenhum requisito, script ou teste DEVE
emular, executar ou instrumentar um binário de firmware. Desempacotar a imagem (ex.:
`binwalk -e`, `unsquashfs`) e ler os arquivos extraídos é análise estática e é
permitido, com os limites do princípio VI.

As features DEVEM vir só do conteúdo da imagem ou de arquivos extraídos dela
estaticamente. Quais features existem é decisão das specs, não desta constituição.

Representações aprendidas dos dados (ex.: embeddings) só entram no modelo reportado
se superarem, na ablation, uma representação simples e explicável da mesma
informação.

Justificativa: a análise dinâmica exige emulação por arquitetura e está fora do
escopo do TCC. Desempacotar e inspecionar arquivos extraídos é a prática da análise
estática de firmware (Costin et al., USENIX Security 2014). Representações aprendidas
custam interpretabilidade e reprodutibilidade, então precisam provar ganho.

### II. Rótulo exclusivamente por CVE

- O alvo do classificador é a classe de vulnerabilidade conhecida via CVE. Fabricante
  e modelo não são alvo.
- O rótulo de treino DEVE vir somente do cache de CVE consultado por fabricante/modelo
  (e versão, quando conhecida).
- Uma consulta ausente no cache é erro, NÃO evidência de que não há CVE conhecida.
- `src/scoring.py` é baseline de regras fixas, sem aprendizado, usado só como
  referência de comparação com os modelos. NÃO DEVE gerar rótulo de treino.

Justificativa: o ground truth precisa ser externo ao classificador e auditável.
A regra de rotulagem é definida pela spec correspondente e implementada em
`src/labeling/`.

### III. Sem vazamento de rótulo ou de partição

- Fabricante, modelo e versão são metadados de consulta e NÃO DEVEM entrar no vetor
  de features, nem com prefixo `meta_`.
- Campos derivados de CVE (`cvss_max`, `cve_total`, `cve_count_*`) NÃO DEVEM entrar
  no vetor de features.
- Colunas de proveniência (`meta_*`) NÃO são features do classificador.
- Nenhuma feature DEVE ser calculada a partir do cache de CVE, da NVD ou de outro
  dado usado para gerar o rótulo.
- Partições (treino, validação, teste) DEVEM ser agrupadas por modelo de
  dispositivo: todos os arquivos e versões de um modelo ficam na mesma partição.
- Todo transformador ajustado a dados (vocabulário, TF-IDF, SVD/PCA, seleção de
  features, scaler, embeddings) DEVE ser ajustado só na partição de treino.
- O conteúdo do binário também codifica identidade (cabeçalhos, SDK, nome do
  modelo). A avaliação DEVE reportar um baseline de identidade (fabricante em
  one-hot, só como diagnóstico, nunca no modelo reportado) e mostrar que o ganho dos
  modelos não vem só da identidade.
- Toda mudança no vetor de features DEVE manter passando o teste de guarda de
  vazamento em `tests/`. Ele confere nomes de colunas; identidade codificada nos
  valores é coberta pelo baseline de identidade.

Justificativa: o rótulo é função de fabricante e modelo. Sem essas regras o
classificador pode aprender a identidade do dispositivo e inflar as métricas sem
medir o conteúdo do binário (Arp et al., USENIX Security 2022: data snooping e
correlações espúrias).

### IV. Modelos simples e explicáveis

- Extra Trees é o modelo principal; Random Forest é o baseline de ML. Hiperparâmetros
  e protocolo de treino ainda não estão definidos e ficam em spec Planejado.
- Deep learning pesado NÃO DEVE ser usado: o dataset é pequeno.
- Outra família de modelo só entra por emenda desta constituição, com justificativa
  acadêmica escrita.

Justificativa: modelos baseados em árvores funcionam com poucas amostras, não exigem
escala comum entre features e expõem importância de features para a banca.

### V. Reprodutibilidade e rastreabilidade

- Toda etapa aleatória DEVE usar semente fixa e registrada em configuração
  versionada.
- Parâmetros de execução DEVEM vir de configuração versionada ou de override
  registrado na linha de comando.
- Artefatos DEVEM ser persistidos nos locais fixos: modelos e embeddings em `models/`,
  tabelas finais em `dataset/processed/` com metadados, resultados em `reports/` com
  timestamp.
- Toda etapa DEVE ser determinística de fato: a mesma entrada e configuração geram a
  mesma saída em processos separados, independentemente da ordem de execução. Fixar
  a semente da biblioteca não basta quando ela depende de outro estado (ex.:
  `PYTHONHASHSEED`).
- Todo transformador treinado (vocabulário, SVD/PCA, embeddings) DEVE ser salvo com
  hiperparâmetros, semente e os `firmware_id` da partição de treino.
- O mapa de rótulos DEVE ser estável entre execuções.
- Splits, tamanho do dataset, contagem de features e parâmetros de modelo DEVEM ser
  registrados via `logging`.

Justificativa: a banca precisa reproduzir cada número apresentado no TCC.

### VI. Firmware é entrada não confiável

- Leituras de binário DEVEM ter limite de tamanho (`max_bytes`) e tratar falha de
  leitura sem derrubar o lote.
- Falha de leitura, binário corrompido ou rótulo inválido DEVEM ficar visíveis no
  artefato ou na exceção (arquivo, fabricante, etapa). Fallback silencioso que
  esconda problema de qualidade de dado é proibido.
- Strings são extraídas como ASCII; nenhuma outra codificação é presumida.

Justificativa: o dataset contém imagens de terceiros, possivelmente malformadas.

### VII. Integridade científica

- Nenhum resultado experimental DEVE ser inventado ou citado sem execução.
- Todo requisito DEVE descrever comportamento que o código tem, ou estar marcado como
  Planejado ou Proposto.
- Toda mudança de escopo, dado ou modelo DEVE ter justificativa acadêmica registrada.

Justificativa: o TCC é avaliado pela validade dos resultados, não pelo volume de
funcionalidade.

## Restrições Técnicas

- Python ≥ 3.9; dependências declaradas em `pyproject.toml` e `requirements.txt`.
- pytest é o executor de testes obrigatório.
- Dependências externas mínimas. A consulta à NVD (`scripts/fetch_cves.py`) é a única
  etapa que usa rede; as etapas seguintes leem o cache local.
- Estilo de código, tipagem, logging e comandos do pipeline seguem o `AGENTS.md`.

## Convenções de Especificação

- **Fonte única de requisitos**: `specs/NNN-nome/` do Spec Kit. NÃO DEVE existir
  `docs/requirements/` nem outra lista paralela de requisitos.
- **Idioma**: pt-br; termos técnicos em inglês são permitidos.
- **Atores**: pesquisador (executa e reproduz o pipeline) e banca (audita).
  Histórias de analista de segurança usando o classificador são Proposto.
- **Diretórios de spec**: nome curto em ASCII via `--short-name` (ex.:
  `001-extracao-features`); o script do Spec Kit descarta letras acentuadas do slug.
- **Requisitos não funcionais**: vêm destes princípios e dos critérios mensuráveis
  `SC-###` de cada `spec.md`.
- **Status**: o campo `**Status**` do `spec.md` DEVE ter um destes valores, no lugar
  de `Draft`:
  - `Implementado`: o comportamento existe no `master`. Cada FR aponta para módulo e
    teste no `plan.md`, ou aparece na lista "sem verificação".
  - `Planejado`: trabalho aceito e ainda não implementado. Cada FR cita a task do
    TickTick de origem (ex.: T03).
  - `Proposto`: ideia sem compromisso de implementação.
  - `Misto`: FRs em estados diferentes. Cada FR leva o próprio status:
    `- **FR-001** [Implementado]: O sistema DEVE ...`.
- **Referência entre specs**: `NNN/FR-###` (ex.: `002/FR-003`). O mesmo vale para
  `NNN/SC-###`.
- **Rastreabilidade**: US → FR → módulo → teste, registrada no `plan.md` (Project
  Structure) e no `tasks.md` de cada spec; `/speckit.analyze` verifica a cobertura.
- **Hierarquia de verdade**:
  1. Código no `master` e seus testes: o que o sistema faz hoje.
  2. Specs em `specs/`: o que o sistema DEVE fazer, com Status.
  3. Documentos em `docs/` (ex.: `PIPELINE.md`, `SCORING.md`): texto explicativo
     sem autoridade. Podem estar desatualizados; servem de pista, não de fonte.
     Requisito tirado de `docs/` DEVE ser conferido no código antes de entrar em
     spec como Implementado. Divergência entre `docs/` e código é defeito de
     documentação, registrado no `TODO.md`.

## Governance

- Esta constituição é a fonte única do escopo imutável do projeto. O `AGENTS.md`
  a importa (`@.specify/memory/constitution.md`) e NÃO DEVE repetir suas regras.
  Mudança de escopo é emenda MAJOR e exige justificativa acadêmica.
- `DEVE`/`NÃO DEVE` equivalem a MUST/MUST NOT da RFC 2119.
- Emendas: alterar este arquivo por `/speckit.constitution`, justificar no commit e
  obter aprovação do pesquisador.
- Versionamento semântico: MAJOR remove ou redefine princípio; MINOR adiciona
  princípio ou seção; PATCH corrige redação.
- Conformidade: todo `plan.md` DEVE passar pelo Constitution Check; violação só entra
  com justificativa na tabela Complexity Tracking. `/speckit.analyze` trata conflito
  com princípio como severidade crítica.

**Version**: 1.0.0 | **Ratified**: 2026-09-24 | **Last Amended**: 2026-09-24
