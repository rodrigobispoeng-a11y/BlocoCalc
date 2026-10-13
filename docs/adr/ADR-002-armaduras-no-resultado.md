# ADR-002 — Armaduras e detalhamento no contrato de resultado (schemas v2)

- Status: aceita (Rodrigo, 13/10/2026)
- Contexto: o motor já calcula tirantes, malha de distribuição e ancoragem
  (`core.strut_tie`, `standards.detailing`), mas `AnalysisResult` v1 só carrega reações,
  verificações e alertas. Sem um campo de armaduras, a interface e o relatório não têm como
  mostrar o resultado principal do dimensionamento. Também faltam na entrada o diâmetro das
  barras e a classe de agressividade ambiental, que o detalhamento precisa.
- Decisão: publicar `schemas` v2 com as mudanças abaixo. A v1 continua lida e é
  convertida para v2 com os valores padrão indicados.
  1. Novo `Reinforcement(id, kind, direction, force_d, area_required, bar_diameter, reference)`,
     com `kind` em {`tie`, `distribution`, `suspension`, `lateral_top`} e `direction` como
     vetor unitário em planta. Um item por tirante e um por direção da malha.
  2. `AnalysisResult.reinforcement: tuple[Reinforcement, ...]`, vazio por padrão.
  3. Novo `DetailingInput(bar_diameter=16, aggressiveness_class="II", hooked=True)`, opcional
     na entrada da análise. O cobrimento continua em `Cap.cover`; uma nova verificação compara
     `Cap.cover` com o cobrimento nominal da NBR 6118:2023, Tab. 7.2, para a classe informada.
  4. `schema_version` passa a `"2"` em todos os modelos.
- Alternativas descartadas: devolver armaduras só em `Check` (mistura demanda de verificação com
  quantidade de aço); guardar o modelo de bielas inteiro no resultado (expõe detalhe interno
  do método e amarra o contrato a Santos/Stucchi).
- Consequências: a suspensão aparece como `kind="suspension"` com área zero e alerta até o
  método de cálculo dela ser pinado. A escolha automática de barras (número e espaçamento nas
  faixas) fica fora desta versão; `area_required` é a área mínima, não a área efetiva.
