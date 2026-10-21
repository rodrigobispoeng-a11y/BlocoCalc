# ADR-014 — Rótulos do modelo de bielas e tirantes na aba 3D e Nk na entrada (schemas v8)

- Status: aceita (aprovada por Rodrigo em 21/10/2026)
- Contexto: a aba 3D (ADR-006) desenha a treliça do M5 com a espessura proporcional à força,
  mas sem números: para saber a força numa biela ou a reação de uma estaca é preciso ir às
  tabelas. O vídeo de referência (21/10/2026) mostra a força escrita em cada barra, as cargas
  nos pilares, as reações nas estacas e as alturas d, h e d′, em tf. É o último dos três ciclos
  visuais (depois da ADR-012 e da ADR-013).
- Decisão:
  1. `viz.scene.CapScene` ganha `labels`: textos com posição e cor, sem Qt. Uma função pura
     `truss_labels(geometry, case, reactions, layout, gamma_n, unit)` monta:
     - em cada biela e tirante, a força de cálculo no meio da barra, na cor da barra;
     - em cada pilar, acima dele, `Nk` (quando informado), `Fd` (a carga da tabela, já
       majorada por γf) e `Nd = γn·Fd` (02-metodos §2, D3);
     - em cada estaca, logo abaixo do bloco, `Rk` (quando há Nk em todos os pilares do caso) e
       `Rd` do caso;
     - numa aresta do bloco, as cotas `h`, `d′` (altura do nó da estaca, camada mais alta de
       tirantes, D20) e `d = h − d′`, com as linhas de cota.
  2. Unidade escolhida na tela: kN (padrão) ou tf, com 1 tf = 9,80665 kN; uma casa decimal. As
     cotas ficam em mm.
  3. Na aba 3D, no modo "modelo de bielas e tirantes": caixa "Rótulos" (ligada) e caixa
     "Forças em tf". Bloco flexível (D9) tem só as reações e as cargas, sem barras e sem d.
  4. Nk e Rk (escolha de Rodrigo no cartão de 21/10/2026, "Coluna Nk"): como γf está
     "Pendente" no 02-metodos (combinações, 11.8.2), o programa não divide Fd por γf. A
     tabela de cargas ganha a coluna opcional "Nk [kN]", a força normal característica (sem
     γf) de cada pilar em cada caso. `schemas` v8: `ColumnLoad.nk: float | None = None` (N,
     positivo em compressão), lendo v1 a v7 sem perda; o `.bloco` grava o campo só quando
     informado, e o hash das entradas de projetos sem Nk não muda.
     `analysis.characteristic_reactions(project, case_id)` calcula Rk pelo M1 (estacas
     rígidas, mesmo método das reações de cálculo) com Nk no lugar de Fd. Premissas, que vão
     para a nota da aba: os momentos e as forças horizontais do caso entram reduzidos na mesma
     razão Nk/Fd de cada pilar (mesmo γf para todos os esforços do pilar); o peso próprio é o
     da D7 aplicado a Nk; sem γn, que é só de cálculo. Sem Nk em algum pilar do caso, não há
     Rk. Nk não muda o dimensionamento e o memorial ganha só a coluna na tabela de cargas.
- Fora do escopo: rótulos no campo de tensões do MEF, ângulo das bielas, tensões nos nós,
  rótulos no memorial e no DXF.
- Alternativas descartadas:
  - Texto 3D extrudado (`pv.Text3D`): gira com o modelo e fica ilegível de lado; os rótulos de
    ponto do VTK sempre encaram a câmera.
  - Mostrar a força só ao passar o mouse: esconde a leitura de conjunto que o vídeo mostra.
- Consequências: `schemas` v8 com um campo opcional; arquivos antigos abrem sem perda e
  arquivos v8 não abrem em versões antigas do programa. Os testes conferem textos e
  posições como dados; a imagem é conferida por renderização fora da tela.
- Plano de PRs: (1) esta ADR; (2) `schemas` v8 com Nk, coluna na tela e no memorial e
  `characteristic_reactions`; (3) `truss_labels` e o desenho dos rótulos; (4) caixas na aba 3D.
  A partir do (2), com base em `main` e com os commits dos ciclos 20 e 21 até eles serem
  mesclados.
