# ADR-014 — Rótulos do modelo de bielas e tirantes na aba 3D

- Status: proposta
- Contexto: a aba 3D (ADR-006) desenha a treliça do M5 com a espessura proporcional à força,
  mas sem números: para saber a força numa biela ou a reação de uma estaca é preciso ir às
  tabelas. O vídeo de referência (21/10/2026) mostra a força escrita em cada barra, as cargas
  nos pilares, as reações nas estacas e as alturas d, h e d′, em tf. É o último dos três ciclos
  visuais (depois da ADR-012 e da ADR-013).
- Decisão:
  1. `viz.scene.CapScene` ganha `labels`: textos com posição e cor, sem Qt. Uma função pura
     `truss_labels(geometry, case, reactions, layout, gamma_n, unit)` monta:
     - em cada biela e tirante, a força de cálculo no meio da barra, na cor da barra;
     - em cada pilar, acima dele, `Fd` (a carga da tabela, já majorada por γf) e
       `Nd = γn·Fd` (02-metodos §2, D3);
     - em cada estaca, logo abaixo do bloco, `Rd` do caso;
     - numa aresta do bloco, as cotas `h`, `d′` (altura do nó da estaca, camada mais alta de
       tirantes, D20) e `d = h − d′`, com as linhas de cota.
  2. Unidade escolhida na tela: kN (padrão) ou tf, com 1 tf = 9,80665 kN; uma casa decimal. As
     cotas ficam em mm.
  3. Na aba 3D, no modo "modelo de bielas e tirantes": caixa "Rótulos" (ligada) e caixa
     "Forças em tf". Bloco flexível (D9) tem só as reações e as cargas, sem barras e sem d.
  4. Nk e Rk (valores característicos) não entram nesta ADR: a tabela de cargas recebe Fd e γf
     ainda está "Pendente" no 02-metodos (combinações, 11.8.2). Entram depois, conforme a
     escolha de Rodrigo no cartão de 21/10/2026, com o próprio PR.
- Fora do escopo: rótulos no campo de tensões do MEF, ângulo das bielas, tensões nos nós,
  rótulos no memorial e no DXF.
- Alternativas descartadas:
  - Texto 3D extrudado (`pv.Text3D`): gira com o modelo e fica ilegível de lado; os rótulos de
    ponto do VTK sempre encaram a câmera.
  - Mostrar a força só ao passar o mouse: esconde a leitura de conjunto que o vídeo mostra.
- Consequências: sem mudança em `schemas` nem no `.bloco`. Os testes conferem textos e
  posições como dados; a imagem é conferida por renderização fora da tela.
- Plano de PRs: (1) esta ADR; (2) `truss_labels` e o desenho dos rótulos; (3) caixas na aba 3D.
  A partir do (2), com base em `main` e com os commits dos ciclos 20 e 21 até eles serem
  mesclados.
