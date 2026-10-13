# BlocoCalc

Aplicativo desktop (Windows) para dimensionamento de blocos de coroamento sobre estacas,
pelo método de bielas e tirantes da ABNT NBR 6118:2023, com verificação independente das
bielas por MEF (fase posterior).

> Uso profissional: o BlocoCalc auxilia o engenheiro. Todo resultado exige revisão por
> engenheiro habilitado e sai acompanhado de método, cláusula normativa e premissas.

## Estado atual

Ciclo 1: base normativa ([docs/02-metodos.md](docs/02-metodos.md)), esqueleto do pacote e
contratos de dados v1. O motor analítico ainda não foi implementado.

## Desenvolvimento

```bash
python -m pip install -e ".[dev]"
make check   # ruff + mypy --strict + pytest
```

Convenções de código e de trabalho: [CLAUDE.md](CLAUDE.md). Decisões de arquitetura:
[docs/adr/](docs/adr/).
