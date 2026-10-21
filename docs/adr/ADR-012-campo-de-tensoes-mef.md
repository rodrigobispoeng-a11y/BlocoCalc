# ADR-012 — Campo de tensões do MEF na aba 3D

- Status: aceita (aprovada por Rodrigo em 21/10/2026)
- Contexto: o objetivo visual do programa (vídeo enviado por Rodrigo em 21/10/2026) é ver o
  bloco pintado pela tensão principal de compressão do MEF, em faixas de cor, como nos
  programas de elementos finitos. O MEF da D14 já resolve o bloco em sólidos C3D10 e
  `fem.post.StressField` já calcula σ3 em cada nó, mas só para somar a tração nos planos e as
  médias nos nós; a malha e as tensões são descartadas no fim de `fem_verification`. A aba 3D
  (ADR-006) só mostra a treliça. Este é o primeiro de três ciclos: depois vêm as ferramentas do
  visualizador (cortes, transparência, deformada, valor no ponto) e os rótulos da treliça.
- Protótipo: renderização fora da tela do B1 (malha padrão, 30 614 nós e 20 072 elementos, 33 s
  de MEF) com a célula quadrática do VTK, que usa a mesma ordem de nós do C3D10 do CalculiX.
  Compressão máxima de 11,0 MPa sob o pilar e as bielas aparecendo no corte pelas estacas.
- Decisão:
  1. Novo contrato transitório em `blococalc.schemas`, como o `StrutTieLayout` da ADR-006, sem
     mudar a versão do arquivo: `FemField(case_id, nodes, tetrahedra, displacements, sigma3)`,
     em tuplas planas para validar rápido. `nodes` e `displacements` têm 3 valores por nó [mm],
     `tetrahedra` 10 índices por elemento na ordem do C3D10, `sigma3` um valor por nó [MPa],
     negativo em compressão, com a média nodal do CalculiX. Os deslocamentos já vêm agora para a
     deformada do próximo ciclo. Ele não entra em `AnalysisResult` nem em `Project`: o `.bloco`
     e o hash das entradas não mudam. Ao abrir um projeto, o campo só volta rodando o MEF de
     novo.
  2. `analysis.fem_verification_with_fields(...) -> (AnalysisResult, tuple[FemField, ...])`,
     com um campo por caso de cálculo. `fem_verification` passa a chamá-la e devolve só o
     resultado, sem mudança para quem já a usa. Bloco flexível não tem campo.
  3. `blococalc.viz.scene.stress_scene(geometry, field) -> CapScene`: o bloco como malha
     não estruturada, pintado pela compressão (−σ3, sem a tração) em 12 faixas de 0 ao máximo
     do caso, na paleta azul-vermelho do vídeo, com os pilares e as estacas em cinza. A tração
     fica na menor faixa: este ciclo mostra só as bielas.
  4. Na aba 3D, um seletor "Exibir: modelo de bielas e tirantes | tensões do MEF". A segunda
     opção só se habilita depois de rodar o MEF nesta sessão, para o caso escolhido. A nota da
     aba mostra a compressão máxima e, como referência, os limites do método já Pinados
     (fcd1 e fcd3, NBR 6118:2023, 22.3.2). O pico sob o pilar é concentração do modelo elástico
     e não é verificação; quem verifica continua sendo o método (D2) e as médias da D14.
- Fora do escopo: gravar o campo no `.bloco` (cerca de 10 MB de JSON por caso no B1), cortes,
  transparência, deformada, valor no ponto (próximo ciclo), tensão de tração σ1 e outras
  componentes.
- Alternativas descartadas:
  - Passar o resultado interno de `fem` direto para `viz`: quebra a regra de que subpacotes só
    trocam modelos de `schemas`.
  - Rodar o MEF de novo dentro da aba 3D: mais 30 a 40 s a cada troca de caso.
  - Gravar o campo no `.bloco` já agora: muda o formato do arquivo e o deixa pesado antes de
    saber se o visual atende.
- Consequências: contrato novo em `schemas`, sem mudar a versão do `.bloco`. A memória da tela
  cresce cerca de 10 MB por caso enquanto o resultado do MEF estiver aberto. Os testes conferem
  o campo e a cena como dados; a imagem é conferida por renderização fora da tela.
- Plano de PRs: (1) esta ADR; (2) `FemField` e `fem_verification_with_fields`; (3) cena
  `stress_scene`; (4) seletor na aba 3D. Todos com base em `main`; cada um inclui os commits
  do anterior até ele ser mesclado.
