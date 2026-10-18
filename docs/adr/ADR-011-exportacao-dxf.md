# ADR-011 — Exportação dos desenhos em DXF

- Status: proposta
- Contexto: o memorial (ADR-005, ADR-008) traz a forma e a armação do bloco (D19, ADR-010)
  como imagens no PDF. Para montar a prancha de execução, o engenheiro ainda redesenha tudo no
  CAD do escritório. Os desenhos já existem em `blococalc.report.drawings` como listas de
  linhas, polilinhas, círculos e textos em mm, nas coordenadas do bloco; falta gravar essa mesma
  geometria num formato que o CAD abra.
- Decisão:
  1. Formato DXF ASCII da versão R12 (AC1009), escrito pelo próprio programa, sem biblioteca
     nova. É a versão que todo CAD abre (AutoCAD, BricsCAD, ZWCAD, LibreCAD, DraftSight) e
     cabe em cerca de 150 linhas de código: cabeçalho, tabela de camadas e entidades `LINE`,
     `POLYLINE`, `CIRCLE` e `TEXT`. Unidade de desenho em mm, escala 1:1 no espaço do modelo.
  2. Uma camada por função, com a cor ACI usada no CAD:

     | Camada | Conteúdo | Cor |
     | --- | --- | --- |
     | `FORMA` | Contorno do bloco e pilares | 7 (branco/preto) |
     | `ESTACAS` | Estacas | 8 (cinza) |
     | `ARM-TIRANTE` | Barras dos tirantes | 5 (azul) |
     | `ARM-MALHA` | Malha e armadura de flexão | 3 (verde) |
     | `COTAS` | Linhas e valores de cota (cm) | 1 (vermelho) |
     | `TEXTOS` | Identificadores, chamados das posições, títulos, tabela de aço | 7 |

  3. `_Sheet` passa a guardar primitivas neutras (linha, polilinha, círculo, círculo cheio,
     texto, com a camada de cada uma) e ganha dois renderizadores: o SVG de hoje, que sai igual
     ao atual (os testes do memorial não mudam), e o DXF. O fundo branco das etiquetas é só do
     SVG; a seção de barra cortada vira um círculo cheio pela polilinha de largura constante
     (o "donut" do R12).
  4. Um único arquivo por análise, com os desenhos lado a lado no espaço do modelo, cada um com
     título: na primeira fila a planta de forma e os cortes de forma em x e y; na segunda a
     planta de armação com os chamados, os cortes de armação em x e y e a tabela de aço com o
     resumo por bitola (mesmos números do memorial). Os desenhos do modelo de bielas e tirantes
     não entram: são para revisão do cálculo, não para a obra.
  5. Textos com altura fixa de 2,5 mm na escala 1:25 (62,5 mm no modelo), a mesma em todos os
     desenhos, e títulos com "ESC. 1:25". No SVG do memorial a altura continua proporcional a
     cada desenho, como hoje. Acentos e "φ" saem em ANSI 1252 (`$DWGCODEPAGE`), com "φ" escrito
     como `%%c`, o símbolo de diâmetro do AutoCAD.
  6. Nova função pura `blococalc.report.dxf.cap_drawing(geometry, positions) -> str`, sem Qt e
     sem I/O, como o resto de `report`. A tela ganha "Arquivo > Exportar desenhos (DXF)...",
     que recalcula como o memorial e grava o texto; bloco sem posições de armação (análise que
     reprovou antes do detalhamento) sai só com a forma, com aviso na barra de estado.
- Fora do escopo: cotas associativas (`DIMENSION`), blocos (`INSERT`), espaço do papel com
  carimbo e escala escolhida pelo usuário, DWG. As cotas saem desenhadas (linhas e texto), como
  no memorial.
- Alternativas descartadas:
  - `ezdxf` (MIT, Python puro, cerca de 5 MB): daria DXF 2010 com cotas associativas e textos
    em UTF-8, mas é dependência nova para o que o R12 já resolve. Pode voltar se o carimbo ou as
    cotas associativas forem pedidos.
  - Converter o SVG do memorial para DXF: perderia as camadas e a escala dos textos.
- Consequências: sem mudança de contrato e sem dependência nova. Os testes leem o DXF como texto
  (camadas, quantidade de barras por posição, comprimentos, chamados); a abertura num leitor de
  DXF independente é conferida à mão e registrada no PR da implementação.
- Plano de PRs: (1) esta ADR; (2) `_Sheet` com primitivas neutras e o SVG sem mudança;
  (3) `report.dxf` com os testes; (4) menu da tela.
