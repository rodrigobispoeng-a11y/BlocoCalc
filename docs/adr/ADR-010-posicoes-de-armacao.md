# ADR-010 — Posições de armação no resultado (schemas v7)

- Status: aceita (Rodrigo, 18/10/2026)
- Contexto: a D19 (docs/02-metodos.md §4.10) desenha a armação e monta a tabela de aço. Para
  isso é preciso saber onde fica cada barra, e só a análise sabe quais tirantes formam uma linha
  de barras contínua (D13). `Reinforcement` (ADR-002, ADR-009) guarda área, φ, quantidade e
  espaçamento, mas não a posição das barras. `report` só pode ler `schemas` (ADR-008).
- Decisão: publicar `schemas` v7, lendo v1 a v6 sem perda.
  1. Novo contrato `BarPosition`: `id` ("N1"), `bar_diameter` [mm], `count`, `length` [mm,
     média quando variável], `variable_length: bool`, `hook: HookShape`, `layer: int` (1 a 3),
     `reinforcement_ids` (as armaduras do resultado que a posição atende) e `bars`, uma tupla
     com as extremidades em planta de cada barra, `((x0, y0), (x1, y1))` em mm.
  2. `HookShape`, enum com a forma escolhida na D19 (90° com ponta de 8φ) e "sem gancho", para
     a entrada sem ganchos.
  3. `AnalysisResult` ganha `bar_positions: tuple[BarPosition, ...] = ()`. Resultados antigos
     abrem sem posições; o hash das entradas não muda, porque o gancho não é entrada neste
     ciclo (é a regra da D19).
  4. O cálculo das linhas é função pura nova em `geometry`, chamada por `analysis`.
- Alternativas descartadas:
  - Recalcular as posições no memorial a partir dos ids `tirante_A_B`: `report` teria de
    refazer a regra das linhas contínuas (D13) e interpretar ids, que não são contrato.
  - Só a tabela de aço, sem coordenadas: não permite desenhar a planta nem conferir a faixa.
- Consequências: `SCHEMA_VERSION` passa a "7". O `.bloco` cresce com as coordenadas (cerca de
  100 barras no B7). Arquivos salvos pela versão nova não abrem em versões antigas.
