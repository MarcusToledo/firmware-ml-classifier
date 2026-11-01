# Pré-registro: cobertura da NVD e proteções de binário (rodada v3)

Registrado em 01/11/2026, antes de qualquer métrica de modelo da rodada v3
(Portão B confirmado pelo pesquisador na mesma data). Análise descritiva, sem
modelo, sem teste de hipótese e sem escolha posterior de recorte.

## Pergunta
A ausência do produto na NVD está associada a firmware mais protegido? A
análise serve para avaliar a hipótese de que "sem CVE/NVD" indica firmware
possivelmente seguro. Qualquer resultado, inclusive a ausência de diferença,
é reportado.

## Grupos (por `firmware_id`, rótulos `labels_v3.csv`)
- A, `nao_encontrado`: `security_level = indeterminado` e
  `evidence_reason = nao_encontrado`.
- B, `sem_cve_confirmado`: `security_level = sem_cve_conhecida` (produto
  reconhecido pela NVD, conforme o Portão A).
- Mesma elegibilidade do corpus, exceto o rótulo: excluir `falha_extracao` e
  `terceiros` (`training_table_exclusions.csv`).

## Variáveis (`features_v2.parquet`, sem recálculo)
`unpacked_prop_nx`, `unpacked_prop_pie`, `unpacked_prop_relro_full`,
`unpacked_prop_relro_partial`, `unpacked_prop_canary`.

## Estatísticas
Por grupo, no total e por fabricante:
- n de `firmware_id` (denominador) e n com valor ausente;
- mediana, quartis 1 e 3 e média, só entre os valores presentes.

Nenhum teste de significância e nenhum limiar de decisão. Fabricantes com
n < 5 num grupo são mostrados, marcados como "n insuficiente".

## Interpretação pré-definida
Diferenças são descritas como associação no corpus, não como causa. Grupos
com composição de fabricante diferente são comparados também dentro de cada
fabricante. O resultado não altera rótulos, regras nem o protocolo da 011.

## Saída prevista
Tabela CSV e parágrafo para a monografia em `reports/` (Fase 9), com SHA256
das entradas.
