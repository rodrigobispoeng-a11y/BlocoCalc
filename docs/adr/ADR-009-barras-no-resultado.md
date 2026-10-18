# ADR-009 — Barras escolhidas no resultado (schemas v6)

- Status: aceita (Rodrigo, 18/10/2026)
- Contexto: a D18 (docs/02-metodos.md §4.9) escolhe as barras de cada armadura. O resultado
  (`Reinforcement`, ADR-002) só tem a área necessária e o diâmetro digitado, e a entrada
  (`DetailingInput`) não tem o agregado graúdo, que a 18.3.2.2 usa no espaçamento livre.
- Decisão: publicar `schemas` v6, lendo v1 a v5 sem perda.
  1. `DetailingInput` ganha `max_aggregate_size: float = 19.0` (> 0, mm). Arquivos antigos
     abrem com brita 1.
  2. `Reinforcement` ganha três campos opcionais, `None` quando a armadura não tem barras
     (suspensão e lateral, D11): `bar_count: int | None` (tirantes), `spacing: float | None`
     (malha e flexão, mm) e `area_provided: float | None` (mm²). `bar_diameter` passa a ser o
     diâmetro escolhido, que pode diferir do digitado conforme a decisão da §4.9.
  3. A versão fixa do hash (ADR-007) passa de "4" para "6": os resultados salvos na v5 não
     têm barras nem a ancoragem com a área efetiva, então ficam marcados como desatualizados e
     são refeitos na próxima análise, como já acontece quando uma entrada muda.
  4. Na tela, "Agregado máx. [mm]" no grupo de detalhamento; na tabela de armaduras, colunas
     "Barras" e "As,ef [cm²]".
- Alternativas descartadas:
  - Calcular as barras só no memorial e na tela, fora do contrato: a ancoragem precisa da área
    efetiva, e o resultado salvo no `.bloco` ficaria sem as barras.
  - Uma lista de camadas por armadura: só faz sentido se a opção (C) da §4.9 for escolhida.
- Consequências: `SCHEMA_VERSION` passa a "6". Arquivos v1 a v5 abrem com as entradas intactas
  e os resultados desatualizados. Arquivos salvos pela versão nova não abrem em versões antigas.
