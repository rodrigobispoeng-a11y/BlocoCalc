# CLAUDE.md — Convenções do Projeto

> Leia antes de qualquer tarefa. Evolução do PLANO.md original (que era só um norte inicial).

## 1. Visão rápida

App desktop local (Windows) para dimensionamento de blocos de coroamento sobre estacas
(N estacas, rígidos ou flexíveis, múltiplos pilares). Motor analítico de bielas e tirantes
(NBR 6118:2023) + verificação de bielas por MEF (gmsh + CalculiX, fase posterior).
Interface PySide6 + PyVistaQt (fase posterior).

Métodos e cláusulas: `docs/02-metodos.md` | Decisões: `docs/adr/`

## 2. Arquitetura

Pacote único (ADR-001):

```
src/blococalc/
├── schemas.py     # contratos v8 (Pydantic, ADR-002 a 004, 006, 007, 009, 010, 012, 014): entradas, resultado, Project
├── analysis.py    # monta a análise completa; única ponte entre core e standards
├── core/          # motor analítico — funções puras, ZERO I/O
├── standards/     # verificações NBR — funções puras
├── geometry/      # geometria paramétrica + pilar fictício — funções puras
├── fem/           # adapters gmsh/ccx (D14; ccx externo: parâmetro, BLOCOCALC_CCX ou PATH)
├── viz/           # cena 3D em malhas PyVista, sem Qt (ADR-006)
├── persistence/   # arquivo de projeto .bloco (ADR-004)
├── report/        # memorial de cálculo em HTML e desenhos SVG (ADR-005, 008) — função pura
└── app/           # PySide6: única camada que conhece Qt (python -m blococalc.app)
tests/             # unit, golden, benchmark
```

Regras de dependência (verificadas em `tests/unit/test_architecture.py`):
- `core`, `standards`, `geometry` e `report` não importam `fem`, `viz`, `persistence` nem `app`;
- `app` é a única camada que conhece Qt;
- Fronteira entre subpacotes: apenas os modelos de `blococalc.schemas`;
- Contratos evoluem por versionamento (v1 -> v2) com ADR, nunca por quebra silenciosa.

## 3. Comandos

```bash
python -m pip install -e ".[dev,app,fem,viz]"   # ou: make setup (conda)
make test        # pytest com cobertura
make lint        # ruff check + ruff format --check
make typecheck   # mypy --strict
make check       # os três
make bench       # benchmarks de validação
```

## 4. Padrões de código

- Python 3.11+, tipagem completa, `mypy --strict` obrigatório;
- `ruff` para lint e formatação (linha 100);
- Funções puras em `core`/`standards`/`geometry`: sem I/O, sem estado global, sem prints;
- Unidades internas fixas: N, mm, MPa. Conversões só nas bordas;
- Toda fórmula normativa tem docstring citando a cláusula (ex.: "NBR 6118:2023, 22.3.2");
- Nomes de código em inglês; comentários, docs e UI em português;
- Sem emojis em código, commits ou docs.

## 5. Testes

- TDD: escreva o teste que falha antes da implementação;
- Golden tests obrigatórios para toda fórmula do motor, com valores recalculados por nós e
  conferidos contra a fonte (as fontes publicadas têm erros: ver 02-metodos.md §5);
- Testes de propriedade: equilíbrio (Σ reações = carga aplicada), simetria;
- Benchmarks em `tests/benchmark/`: reações < 1 %, armaduras < 2 %;
- Proibido editar golden files sem justificativa documentada no PR;
- Cobertura mínima em `core` e `standards`: 90 %.

## 6. Proibições

- Não alterar `blococalc.schemas` sem ADR aprovado;
- Não editar golden files sem justificativa documentada;
- Não fazer merge sozinho: todo PR passa por revisão humana;
- Não instalar dependências novas sem atualizar `pyproject.toml` e registrar no PR;
- Não inventar valores normativos: se a cláusula não está **Pinada** em
  `docs/02-metodos.md`, pergunte;
- Não versionar PDFs das normas (licenciadas).

## 7. Protocolo de trabalho

1. Leia a issue e a seção correspondente de `docs/02-metodos.md`;
2. Escreva o teste que falha;
3. Implemente o mínimo para passar;
4. Rode `make check`;
5. PR pequeno (< 400 linhas), com descrição do que e do porquê;
6. Aguarde revisão humana.

## 8. Segurança de engenharia

- Defaults conservadores (ex.: γn = 1,2, decisão D3);
- Bloqueie com aviso explícito quando uma premissa for violada (ex.: bloco classificado como
  flexível e o usuário pediu modelo rígido);
- Toda saída lista: método, cláusula, premissas, versão dos parâmetros;
- Disclaimer de uso profissional em todos os resultados;
- Trilha de auditoria por análise (`AuditTrail`).
