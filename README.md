# BlocoCalc

Aplicativo desktop (Windows) para dimensionamento de blocos de coroamento sobre estacas,
pelo método de bielas e tirantes da ABNT NBR 6118:2023, com verificação independente das
bielas por MEF (fase posterior).

> Uso profissional: o BlocoCalc auxilia o engenheiro. Todo resultado exige revisão por
> engenheiro habilitado e sai acompanhado de método, cláusula normativa e premissas.

## Estado atual

Motor de bloco rígido sobre 2, 3 ou 4 estacas com um pilar (Santos/Stucchi, NBR 6118:2023),
detalhamento e primeira tela PySide6. Bloco flexível e vários pilares em andamento
(decisões D9 e D10 em [docs/02-metodos.md](docs/02-metodos.md)).

## Desenvolvimento

```bash
python -m pip install -e ".[dev,app]"
make check   # ruff + mypy --strict + pytest
python -m blococalc.app   # abre a tela (ou o comando blococalc)
```

Convenções de código e de trabalho: [CLAUDE.md](CLAUDE.md). Decisões de arquitetura:
[docs/adr/](docs/adr/).
