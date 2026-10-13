# ADR-001 — Pacote único `blococalc` com subpacotes

- Status: aceita (Rodrigo, 13/10/2026)
- Contexto: o PLANO.md inicial previa seis pacotes separados em `packages/` (core, standards,
  geometry, fem, viz, persistence) mais `apps/desktop`. Com um único desenvolvedor e nenhum
  consumidor externo dos pacotes, isso multiplica pyprojects, versões e configuração de CI sem
  ganho real.
- Decisão: um único pacote instalável `blococalc` (layout `src/`), com os mesmos subpacotes:
  `core`, `standards`, `geometry`, `fem`, `viz`, `persistence` e `app`. Os contratos entre eles
  ficam em `blococalc.schemas`.
- Regras mantidas: `core`, `standards` e `geometry` não importam `fem`, `viz`, `persistence`,
  `app` nem bibliotecas de UI/3D/MEF. A regra é verificada por teste
  (`tests/unit/test_architecture.py`), não só por convenção.
- Consequências: dividir em pacotes separados continua possível depois, se algum subpacote
  precisar de ciclo de versão próprio. Até lá, uma versão só para o app inteiro.
