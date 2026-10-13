# ADR-003 — Armadura de flexão de bloco flexível no contrato (schemas v3)

- Status: proposta
- Contexto: o bloco flexível (D9, docs/02-metodos.md §4.2) é dimensionado à flexão nas seções S1
  do CEB-70, não por tirantes. `ReinforcementKind` v2 só tem `tie`, `distribution`, `suspension`
  e `lateral_top`; marcar a armadura de flexão como `tie` faria a interface e o relatório tratarem
  uma armadura distribuída em toda a largura como se estivesse concentrada nas faixas sobre as
  estacas. A trilha de auditoria também precisa dizer qual método foi usado em cada análise.
- Decisão: publicar `schemas` v3, lendo v1 e v2 sem perda.
  1. Novo membro `ReinforcementKind.FLEXURE = "flexure"`: armadura inferior distribuída em toda
     a largura do bloco, um item por direção (`flexao_x`, `flexao_y`). A armadura secundária de
     20 % continua como `distribution`.
  2. `AuditTrail.method` passa a valer `"ceb70-nbr6118-flexao"` para bloco flexível; o valor
     `"santos-stucchi-2019"` continua para o rígido. Sem mudança de tipo.
  3. `schema_version` passa a `"3"`; o validador de versão aceita "1", "2" e "3".
- Alternativas descartadas: reutilizar `tie` (semântica errada para detalhamento); campo novo
  `AnalysisResult.flexible_design` com o modelo inteiro (amarra o contrato ao CEB-70).
- Consequências: a interface precisa desenhar `flexure` como malha uniforme. Os ids de
  verificação novos (`flexao_*`, `cisalhamento_*`, `puncao_C`, `puncao_C1`) não mudam o contrato.
