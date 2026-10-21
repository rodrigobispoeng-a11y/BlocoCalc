# ADR-013 — Ferramentas do visualizador de tensões do MEF

- Status: aceita (aprovada por Rodrigo em 21/10/2026)
- Contexto: a ADR-012 pinta o bloco pela compressão do MEF na aba 3D. Visto de fora, porém, o
  bloco fica quase todo na menor faixa: as bielas correm por dentro e só aparecem num corte, e o
  pico sob o pilar (concentração do modelo elástico) estica a escala. O vídeo de referência
  (21/10/2026) mostra as ferramentas que resolvem isso: planos de corte em x e y, transparência,
  deformada com fator de escala e o valor da tensão no ponto apontado. Este é o segundo de três
  ciclos; depois vêm os rótulos da treliça.
- Decisão:
  1. Nova `blococalc.viz.scene.StressView` (dataclass da cena, sem Qt, fora de `schemas`, como
     `CapScene`): `cut_x` e `cut_y` (posição do plano em mm ou `None`), `opacity` (0,1 a 1),
     `deformation` (fator de ampliação dos deslocamentos, 0 = sem deformada) e `scale_max`
     (topo da escala em MPa ou `None` para o pico do caso). `stress_scene(geometry, field,
     view)` aplica tudo e continua pura e testável como dados.
  2. Corte: cada plano ligado retira a parte do bloco além dele (x > `cut_x`, y > `cut_y`); com
     os dois ligados fica o canto x ≤ `cut_x` e y ≤ `cut_y`. A face cortada mostra as faixas do
     interior. Pilares e estacas não são cortados e ficam semitransparentes quando há corte.
  3. Deformada: os nós do bloco andam `deformation` vezes o deslocamento do MEF (já guardado no
     `FemField`); o corte vale na posição original. A nota da aba mostra o deslocamento máximo
     real em mm, para não confundir o desenho ampliado com o valor.
  4. Escala: `scale_max` menor que o pico satura em vermelho o que passa dele e espalha as 12
     faixas pela região das bielas; a barra de cores mostra o topo escolhido e a nota continua
     com o pico real.
  5. Valor no ponto: `viz.scene.value_at(scene, point)` devolve o nó mais próximo do ponto
     clicado com σ3, a compressão e o deslocamento. Na tela, clique com o botão esquerdo sobre o
     bloco mostra numa linha abaixo do desenho: "σ3 = −8,2 MPa (compressão 8,2 MPa), u = 0,41 mm
     em (x, y, z)". Clique e não passagem do mouse, porque procurar o nó a cada movimento numa
     malha de 50 mil nós pesa na tela.
  6. Na aba 3D, uma segunda barra só no modo "tensões do MEF": "Corte x" e "Corte y" (caixa de
     ligar e controle deslizante de uma face à outra do bloco), "Opacidade", "Deformada ×" e
     "Escala até [MPa]" (vazio = pico). Mudar um controle refaz só a cena, sem rodar o MEF.
- Fora do escopo: plano de corte em z ou inclinado, várias seções ao mesmo tempo, tensão de
  tração σ1 e outras componentes, animação da deformada, valor sob o mouse sem clicar, gravar a
  vista no `.bloco`.
- Alternativas descartadas:
  - Widget de plano interativo do PyVista (`add_mesh_clip_plane`): arrasta o plano na cena, mas
    prende a lógica ao `QtInteractor`, sem como testar como dados e sem o corte em y fixo.
  - Fatiar em vez de cortar (`slice`): mostra só um plano solto, sem o volume em volta que dá a
    leitura das bielas chegando às estacas.
- Consequências: sem mudança em `schemas` nem no `.bloco`. A cena ganha parâmetros e a aba uma
  barra de controles; os testes conferem a cena e o valor no ponto como dados e a barra com o
  plotter falso. A imagem é conferida por renderização fora da tela.
- Plano de PRs: (1) esta ADR; (2) `StressView` e `value_at` na cena; (3) barra de controles e
  clique na aba 3D. A partir do (2), com base em `main` e com os commits do ciclo 20 até eles
  serem mesclados.
