# Data Model: Embeddings Doc2Vec

Artefatos desta spec no código atual em `master`: o modelo
`models/doc2vec.model`, gravado pelo treino (spec, FR-006), e as colunas
`doc2vec_*` que a extração grava em `features.parquet` (spec, FR-008).

## Modelo `models/doc2vec.model`

Gravado pelo `save` do gensim (4.4.0 no `.venv`): um pickle do objeto
`Doc2Vec`. Arrays com pelo menos 10·1024² elementos vão para arquivos
`.npy` ao lado, com nome derivado do arquivo e do atributo (ex.:
`doc2vec.model.wv.vectors.npy`; `gensim/utils.py::SaveLoad._save_specials`).
O path segue `--output` > `doc2vec.model_path` > `models/doc2vec.model`.
Hoje o arquivo não existe (nem a pasta `models/`; conferido em 2026-09-24).

|Conteúdo|Gravado?|Origem|
|---|---|---|
|Vocabulário e pesos (vetores de palavra e camada de saída)|sim|treino sobre os tokens do corpus|
|Um vetor de documento por tag, de `vector_size` posições|sim|tags = `firmware_id` (SHA256 dos bytes lidos, `001/FR-004`) dos documentos de treino|
|`vector_size`, `window`, `epochs`, `min_count`, `dm`, `alpha`, `min_alpha`, `workers`|sim, como atributos do objeto gensim|`doc2vec.*` da configuração|
|Estado aleatório interno (`model.random`)|sim, no ponto em que o treino terminou|semeado por `doc2vec.seed` na criação; avança a cada inferência depois da carga|
|`seed`|sim, como atributo `seed` do objeto gensim|`doc2vec.seed`|
|Limites do corpus (`max_bytes`, `feature.min_string_len`, `feature.max_single_string_len`, `feature.max_strings`, `feature.max_doc_chars`)|não|—|
|`PYTHONHASHSEED` do processo|não|—|
|Lista de paths do corpus e identificação da partição de treino|não|não existe partição: o corpus é toda a entrada|
|Arquivo separado de embeddings alinhados a `firmware_id`|não|os vetores de documento só existem dentro do modelo|

### O que falta segundo o princípio V

O princípio V pede que o transformador seja salvo "com hiperparâmetros,
semente e os `firmware_id` da partição de treino". Hoje:

- Hiperparâmetros e semente: gravados, mas só como atributos internos do
  gensim; não há arquivo de metadados legível sem carregar o modelo.
- `firmware_id` de treino: as tags dos vetores de documento são os
  `firmware_id` do corpus, mas o corpus é toda a entrada, não uma partição
  de treino, e aliases repetidos aparecem uma vez só nas tags (spec, Edge
  Cases).
- A semente não basta para reproduzir a inferência: falta `PYTHONHASHSEED`
  e o estado `model.random` muda a cada chamada (spec, Edge Cases; FR-012,
  Proposto, T06).
- Os limites que definem o documento não são gravados; uma extração com
  `feature.*` diferente infere vetores de documentos que o modelo não viu
  nesse formato. Os três pontos acima são FR-013 (Proposto, T06).

## Colunas `doc2vec_*` em `features.parquet`

|Coluna|Tipo|Valor|
|---|---|---|
|`doc2vec_0` … `doc2vec_{n-1}`|float|vetor inferido do documento do firmware; `n` é a dimensão do modelo carregado|
|`meta_doc2vec_used`|bool|`True` se havia modelo carregado e a leitura deu certo (`001/FR-009`)|

Com a configuração versionada atual, `n = vector_size = 100`. Com
`001/FR-018` (Planejado), a configuração versionada desliga o Doc2Vec e
não há colunas `doc2vec_*`.

## Regras de validação

- Sem modelo: as `vector_size` colunas `doc2vec_*` são 0.0 e
  `meta_doc2vec_used=False` em toda linha.
- Com modelo e documento sem tokens: as `vector_size` colunas da
  configuração são 0.0 e `meta_doc2vec_used=True`.
- Linha de exceção inesperada na extração: sem features (colunas
  `doc2vec_*` nulas na tabela) e `meta_doc2vec_used=False`.
- Nenhuma checagem confere a dimensão do modelo com `doc2vec.vector_size`
  (spec, Edge Cases).

## Artefatos existentes

Medido em 2026-09-24:

|Artefato|Linhas|Colunas `doc2vec_*`|Linhas com vetor todo zero|`meta_doc2vec_used=False`|
|---|---|---|---|---|
|`features.parquet`|840|100|840|840|
|`features_v2.parquet`|840|100|840|840|
