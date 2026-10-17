# ADR-008 — Desenhos do bloco no memorial

- Status: aceita (Rodrigo, 2026-10-17)
- Contexto: o memorial (ADR-005) só tem tabelas. Para revisar o cálculo, o engenheiro precisa
  ver a geometria e o modelo de bielas e tirantes: onde estão as estacas, de onde saem as
  bielas, por onde passam os tirantes e com que força. Hoje isso só aparece na aba 3D (ADR-006),
  que não vai para o papel. O ADR-005 deixou os desenhos para depois da visualização 3D.
- Protótipo: o `QTextDocument` que já imprime o memorial aceita uma imagem SVG embutida no
  próprio HTML (`<img src="data:image/svg+xml;base64,...">`). A Qt rasteriza o SVG pelo plugin
  `qsvg`, que já vem no PySide6, a cerca de 380 ppi no PDF. Não precisa de dependência nova nem
  de mudança na impressão.
- Decisão:
  1. Novo módulo puro `blococalc.report.drawings`, que gera SVG em texto a partir dos contratos
     de `schemas`. Sem Qt e sem I/O, como o resto de `report`. As cotas são em cm, como nos
     desenhos de forma; as forças são em kN.
  2. Desenhos, em escala, com o norte do desenho no eixo y:
     1. Planta de forma: contorno do bloco, estacas (círculo ou quadrado) e pilares com os
        identificadores, cotas totais Lx e Ly e cotas das posições das estacas a partir do
        centro.
     2. Cortes de forma em x e em y pelo centro: altura h, embutimento da estaca, cobrimento e
        eixo do tirante (D8).
     3. Modelo de bielas e tirantes de cada caso, em planta e em corte, desenhado a partir do
        `StrutTieLayout` (ADR-006). As bielas aparecem em vermelho e os tirantes em azul, cada
        um com a força de cálculo em kN, e as estacas trazem a reação. Blocos flexíveis (D9) não
        têm esse desenho, só a forma.
  3. `calculation_report(project, issued, layouts=None)`: a tela passa os `StrutTieLayout`
     de cada caso, calculados por `analysis.strut_tie_layout`. Assim `report` continua
     importando só `schemas`. Os desenhos de forma entram na seção 1 (Entradas) e os do modelo
     numa seção nova, logo depois das reações.
  4. A tela confere se o formato SVG está disponível na Qt. Se não estiver, o memorial sai sem
     desenhos e a barra de estado avisa.
- Fora do escopo: detalhamento das barras (posição, dobras, comprimentos e quantidades), porque
  o programa ainda não escolhe as barras, só a área necessária; e exportação para DXF ou CAD.
- Alternativas descartadas:
  - matplotlib para gerar PNG: dependência nova (cerca de 40 MB) para desenhar linhas e textos.
  - Captura da cena 3D (PyVista): exige OpenGL no momento de gerar o memorial e uma perspectiva
    não se mede como um desenho em escala.
  - Desenhar com `QPainter` direto no PDF: o desenho ficaria dentro de `app`, fora dos testes
    sem tela, e misturado com a paginação do `QTextDocument`.
- Consequências: sem mudança de contrato e sem dependência nova. O PDF cresce cerca de 150 kB
  por desenho. Os testes conferem o SVG como texto (escala, cotas e forças), sem renderizar.
