"""Análise linear do bloco pelo CalculiX (D14, docs/02-metodos.md §4.5).

Escreve o arquivo de entrada (.inp), executa o `ccx` como processo externo num diretório
temporário e lê deslocamentos, tensões e reações do resultado (.frd). O executável vem do
parâmetro `ccx`, da variável de ambiente BLOCOCALC_CCX ou do PATH, nessa ordem.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from blococalc.fem.mesh import CapMesh, FloatArray

POISSON = 0.2  # NBR 6118:2023, 8.2.9
CCX_ENV = "BLOCOCALC_CCX"


class FemError(RuntimeError):
    """Falha ao localizar, executar ou ler o CalculiX."""


@dataclass(frozen=True)
class FemResult:
    displacements: FloatArray  # (n, 3) [mm]
    stresses: FloatArray  # (n, 6) xx, yy, zz, xy, yz, zx nos nós [MPa]
    reactions: FloatArray  # (n, 3) forças nodais RF [N]: reações só nos nós apoiados


def secant_modulus(fck: float) -> float:
    """Ecs = αi·Eci, Eci = αE·5600·√fck, αi = 0,8 + 0,2·fck/80 ≤ 1, αE = 1,0 [MPa].

    NBR 6118:2023, 8.2.8 (válida para fck ≤ 50 MPa; acima, o MEF é só comparativo).
    """
    alpha_i = min(0.8 + 0.2 * fck / 80.0, 1.0)
    return alpha_i * 5600.0 * math.sqrt(fck)


def find_ccx(ccx: str | None = None) -> str | None:
    """Caminho do executável do CalculiX ou None se não houver."""
    candidate = ccx or os.environ.get(CCX_ENV) or "ccx"
    return shutil.which(candidate)


def solve(mesh: CapMesh, forces: FloatArray, fck: float, ccx: str | None = None) -> FemResult:
    """Resolve o bloco elástico linear com apoios verticais nas estacas."""
    executable = find_ccx(ccx)
    if executable is None:
        raise FemError(f"CalculiX não encontrado (parâmetro, {CCX_ENV} ou PATH)")
    with tempfile.TemporaryDirectory(prefix="blococalc-") as folder:
        job = Path(folder) / "bloco"
        job.with_suffix(".inp").write_text(
            input_deck(mesh, forces, secant_modulus(fck)), encoding="ascii"
        )
        run = subprocess.run(
            [executable, "-i", job.name], cwd=folder, capture_output=True, text=True, check=False
        )
        frd = job.with_suffix(".frd")
        if run.returncode != 0 or not frd.exists():
            raise FemError(f"CalculiX falhou ({run.returncode}): {run.stdout[-500:]}")
        return read_frd(frd.read_text(encoding="ascii", errors="replace"), len(mesh.nodes))


def input_deck(mesh: CapMesh, forces: FloatArray, modulus: float) -> str:
    """Arquivo .inp: nós numerados a partir de 1 na ordem de `mesh.nodes`."""
    lines = ["*NODE, NSET=NALL"]
    lines += [f"{i + 1},{x:.6f},{y:.6f},{z:.6f}" for i, (x, y, z) in enumerate(mesh.nodes)]
    lines.append("*ELEMENT, TYPE=C3D10, ELSET=EALL")
    lines += [f"{i + 1}," + ",".join(str(n + 1) for n in tet) for i, tet in enumerate(mesh.tets)]
    for k, nodes in enumerate(mesh.pile_nodes.values()):
        lines.append(f"*NSET, NSET=PILE{k}")
        lines += [str(n + 1) for n in nodes]
    lines += [
        "*MATERIAL, NAME=CONCRETO",
        "*ELASTIC",
        f"{modulus:.6g},{POISSON}",
        "*SOLID SECTION, ELSET=EALL, MATERIAL=CONCRETO",
        "*STEP",
        "*STATIC",
        "*BOUNDARY",
    ]
    lines += [f"PILE{k},3,3,0" for k in range(len(mesh.pile_nodes))]
    lines += [f"{node + 1},{dof},{dof},0" for node, dof in horizontal_supports(mesh)]
    lines.append("*CLOAD")
    for i, row in enumerate(forces):
        lines += [f"{i + 1},{dof + 1},{value:.6f}" for dof, value in enumerate(row) if value]
    lines += ["*NODE FILE", "U,RF", "*EL FILE", "S", "*END STEP", ""]
    return "\n".join(lines)


def horizontal_supports(mesh: CapMesh) -> list[tuple[int, int]]:
    """Vinculação horizontal isostática: x e y num nó, e a direção transversal no mais distante.

    O primeiro nó é o do centro da primeira estaca; o segundo é o nó de estaca mais afastado
    dele, impedido na direção perpendicular à maior projeção da linha entre os dois (impede o
    giro em torno de z). Com cargas equilibradas, as reações horizontais saem iguais a H.
    """
    first = next(iter(mesh.pile_nodes.values()))
    xy = mesh.nodes[:, :2]
    center = xy[first].mean(axis=0)
    a = int(first[np.argmin(np.linalg.norm(xy[first] - center, axis=1))])
    candidates = np.unique(np.concatenate(list(mesh.pile_nodes.values())))
    b = int(candidates[np.argmax(np.linalg.norm(xy[candidates] - xy[a], axis=1))])
    dx, dy = np.abs(xy[b] - xy[a])
    return [(a, 1), (a, 2), (b, 2 if dx >= dy else 1)]


def read_frd(text: str, n_nodes: int) -> FemResult:
    """Lê os blocos DISP, STRESS e FORC do .frd (formato ASCII, campos de 12 colunas)."""
    blocks = {"DISP": 3, "STRESS": 6, "FORC": 3}
    found: dict[str, FloatArray] = {}
    current: str | None = None
    for line in text.splitlines():
        if line.startswith(" -4"):
            name = line.split()[1]
            current = name if name in blocks else None
            if current:
                found[current] = np.zeros((n_nodes, blocks[current]))
        elif line.startswith(" -3"):
            current = None
        elif current and line.startswith(" -1"):
            node = int(line[3:13]) - 1
            width = blocks[current]
            found[current][node] = [float(line[13 + 12 * i : 25 + 12 * i]) for i in range(width)]
    missing = set(blocks) - set(found)
    if missing:
        raise FemError(f"resultado do CalculiX sem os blocos {sorted(missing)}")
    return FemResult(found["DISP"], found["STRESS"], found["FORC"])
