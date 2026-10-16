# ADR-006 — Visualização 3D do bloco e do modelo de bielas e tirantes

- Status: aceita (Rodrigo, 16/10/2026)
- Contexto: a tela mostra o bloco só em tabelas. Para conferir a entrada (estaca fora do lugar,
  pilar trocado de eixo) e entender o resultado (por onde a carga desce, qual tirante governa),
  o engenheiro precisa ver o bloco em 3D. O CLAUDE.md já prevê PyVista/VTK em `viz` e PyVistaQt
  na tela, mas nada foi implementado. Hoje o `AnalysisResult` não guarda a posição dos nós nem
  das barras do modelo de bielas e tirantes: elas existem só dentro de `core.strut_tie` durante
  a análise.
- Decisão:
  1. Novo contrato transitório em `blococalc.schemas`, sem mudar a versão do arquivo:
     `StrutTieLayout(case_id, nodes, members)`, com `LayoutNode(id, x, y, z)` em mm e
     `LayoutMember(id, kind, start, end, force_d)`, onde `kind` é `strut` ou `tie` e `force_d` é
     a força de cálculo em N. Ele não entra em `AnalysisResult` nem em `Project`: o `.bloco`
     (ADR-004) e o hash das entradas não mudam.
  2. `analysis.strut_tie_layout(project, case_id) -> StrutTieLayout | None` refaz o modelo M5
     (Santos/Stucchi, D13, D15) do caso pedido e devolve a geometria: nó superior de cada
     biela na profundidade y/2 abaixo do topo, nó de cada estaca na altura do tirante
     (cobrimento + φ/2 acima da cabeça), tirantes entre os nós das estacas. Devolve `None`
     para bloco flexível (D9), que não tem treliça. Vários pilares usam o pilar fictício (D10),
     o mesmo modelo do dimensionamento.
  3. `blococalc.viz.scene.cap_scene(geometry, reactions, layout) -> CapScene`: monta as malhas
     PyVista (sem janela e sem Qt) do bloco translúcido, dos pilares, das estacas cortadas no
     embutimento, das bielas em vermelho e dos tirantes em azul, com espessura proporcional à
     força. As estacas recebem cor pela reação do caso. Sem `layout`, a cena tem só a
     geometria e as reações.
  4. Na tela, nova aba "3D" com `pyvistaqt.QtInteractor`, seletor de caso de cálculo, botões de
     vista (isométrica, planta, frente, lateral) e legenda de cores. A cena se refaz quando o
     cálculo muda. Se o PyVista não estiver instalado ou o OpenGL falhar, a aba mostra o motivo
     e o resto do programa funciona normalmente.
  5. Dependências novas no extra opcional `viz`: `pyvista>=0.44` e `pyvistaqt>=0.11` (trazem
     VTK, wheel de cerca de 140 MB). A instalação completa passa a ser
     `python -m pip install -e ".[app,fem,viz]"`; o CI instala os três.
- Alternativas descartadas:
  - Gravar a treliça no `AnalysisResult` (schemas v5): aumenta o `.bloco` e o contrato para algo
    que se recalcula em milissegundos a partir das entradas.
  - Matplotlib 3D: mais leve, mas a rotação é lenta e não há transparência confiável para ver
    as bielas dentro do bloco.
  - Qt 3D ou Qt Data Visualization: fora do `PySide6-Essentials`, exigiria o pacote completo do
    PySide6 e escrever a cena do zero.
  - Desenho 2D (planta e cortes) com QPainter: útil para o memorial, mas não mostra as bielas
    cruzando o bloco; fica para depois, sobre a mesma `StrutTieLayout`.
- Consequências: `schemas` ganha dois modelos sem mudar `SCHEMA_VERSION`. `viz` depende de
  `pyvista` e de `schemas`; continua sem importar `app` nem `persistence`, e só `app` conhece
  Qt (`pyvistaqt` fica restrito a `app`). Os testes de `viz` conferem as malhas (contagem,
  limites, cores) sem abrir janela; o teste da aba aceita o aviso de OpenGL indisponível no CI.
  Desenhos do bloco no memorial (ADR-005) passam a ter de onde sair.
- Implementação, em PRs separados: (a) este ADR; (b) contrato e `analysis.strut_tie_layout`;
  (c) `viz.scene`; (d) aba 3D na tela.
