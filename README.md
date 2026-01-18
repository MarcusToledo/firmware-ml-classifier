# Classificação de Firmware (TCC)

## Visão geral
Este repositório corresponde a um Trabalho de Conclusão de Curso (TCC)
de Engenharia de Software focado em classificação automatizada de
firmwares embarcados usando análise estática e aprendizado de máquina.

## Objetivos
- Classificar firmware por fabricante (supervisionado).
- Extrair features estatísticas de binários (tamanho, entropia, bytes).
- Extrair strings ASCII e embeddings Doc2Vec para features semânticas.
- Treinar modelos Extra Trees (principal) e Random Forest (baseline).

## Pipeline experimental
1. Coleta e organização de dataset por fabricante.
2. Extração de features estatísticas e strings.
3. Treino de embeddings Doc2Vec (DM/DBOW) por firmware.
4. Treino e avaliação de modelos supervisionados.
5. Geração de métricas e relatórios.

## Como executar
Instalar dependências:
- `python -m pip install -r requirements.txt`

Executar pipeline (placeholders):
- `python scripts/build_dataset.py`
- `python scripts/sample_dataset.py`
- `python scripts/train.py`

Testes (placeholders):
- `python -m pytest`
- `python -m pytest tests/path::test_name`

