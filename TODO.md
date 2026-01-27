# TODO

## Request: Create/Improve AGENTS.md and establish TODO tracking

### Completed
- [x] Review existing `AGENTS.md` and `README.md` for current guidance and commands.
- [x] Update `AGENTS.md` with build/lint/test commands, code style guidelines, and TODO tracking rules.
- [x] Confirm no Cursor/Copilot rules are present and document that in `AGENTS.md`.

### Pending
- [ ] None.

## Request: Add pt-br only response rule

### Completed
- [x] Add rule requiring pt-br responses with only technical English terms in `AGENTS.md`.

### Pending
- [ ] None.

## Request: Persistir features extraidas

### Completed
- [x] Adicionar exportacao das features com metadados (parquet/csv) no CLI.
- [x] Renomear metadados de label para brand/model/label e ajustar inferencia.
- [x] Incluir meta_bytes_used e meta_max_bytes para rastrear limites aplicados.
- [x] Atualizar testes com novos metadados e flag label-from-path.

### Pending
- [ ] None.

## Request: Feature extraction skeleton

### Completed
- [x] Create feature extraction modules and functions for static features and Doc2Vec.
- [x] Add unit tests with pytest for statistics, strings, and io_utils.
- [x] Update string extraction with max_string_len and normalization.
- [x] Expand string extraction tests for limits and normalization.
- [x] Add compressibility level validation and logging.
- [x] Mark truncation when string or document limits apply.
- [x] Seed Doc2Vec inference for deterministic embeddings.
- [x] Reuse strings_to_document in feature extraction.
- [x] Add YAML-based pipeline config with overrides.
- [x] Add CLI entry for batch feature extraction.
- [x] Add pipeline tests for config, extraction, and CLI.
- [x] Add Doc2Vec unit tests with realistic tokens and determinism checks.
- [x] Add Doc2Vec training CLI script.

### Pending
- [ ] Adjust default limits (`max_strings`, `max_doc_chars`) after dataset profiling.

## Request: Remover duplicacao de utilitarios CLI

### Completed
- [x] Centralizar parse_overrides e gather_paths em `src/cli_utils.py`.
- [x] Atualizar scripts para reutilizar utilitarios CLI.

### Pending
- [ ] None.

## Request: Organizacao de imports

### Completed
- [x] Reordenar imports por grupo (stdlib/third-party/local) em arquivos relevantes.

### Pending
- [ ] None.

## Request: Configuracao e packaging

### Completed
- [x] Adicionar `pyproject.toml` com metadata, dependencias e entry points.
- [x] Criar pacote `scripts` para entry points.
- [x] Adicionar versoes minimas em `requirements.txt`.
- [x] Refatorar `scripts/inspect_tokens.py` para reutilizar utilitarios CLI.

### Pending
- [ ] None.

## Request: Documentacao de codigo

### Completed
- [x] Atualizar docstrings de funcoes publicas.
- [x] Adicionar secao API Interna no README.

### Pending
- [ ] None.

## Request: Consistencia de termos

### Completed
- [x] Ajustar README para incluir --output nos exemplos de extracao.
- [x] Alinhar descricao de features com o que o pipeline gera.
- [x] Atualizar descricao do projeto em pyproject.toml com acentos.

### Pending
- [ ] None.

## Request: Pipeline incompleto

### Completed
- [ ] None.

### Pending
- [ ] Implementar script de treino de modelos (Extra Trees e Random Forest).
- [ ] Implementar script de avaliacao com metricas e confusion matrix.
- [ ] Implementar split train/val/test com seeds fixos.
- [ ] Implementar geracao de relatorios em reports/.

## Request: Qualidade e ferramentas

### Completed
- [x] Adicionar ruff, black, mypy e pre-commit em pyproject.toml.
- [x] Criar .pre-commit-config.yaml com hooks.
- [x] Criar src/py.typed para PEP 561.
- [x] Atualizar README com secao de qualidade.

### Pending
- [ ] None.
