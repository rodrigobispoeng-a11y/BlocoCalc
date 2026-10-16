# ADR-005 — Memorial de cálculo em PDF

- Status: proposta (aguarda aprovação de Rodrigo)
- Contexto: o resultado só existe na tela e no arquivo `.bloco` (ADR-004). Para anexar ao
  projeto e passar pela revisão de um engenheiro habilitado, o cálculo precisa sair num
  documento estável que liste método, cláusulas, premissas, versão dos parâmetros e o aviso de
  uso profissional (CLAUDE.md §8). Hoje nada no programa gera esse documento.
- Decisão:
  1. Novo subpacote `blococalc.report`, função pura `calculation_report(project) -> str` que
     monta o memorial em HTML simples (títulos, parágrafos e tabelas, sem script nem recurso
     externo) a partir de um `Project` (ADR-004). Sem I/O e sem Qt; importa só
     `blococalc.schemas`. Unidades na saída: kN, kN·m, mm, MPa e cm², as mesmas da tela.
  2. Conteúdo, nesta ordem:
     1. Identificação: nome e observações do projeto, data de emissão, versão do programa e o
        aviso de uso profissional (`AnalysisResult.disclaimer`).
     2. Entradas: bloco, materiais (fck, fyk, γc, γs), estacas, pilares, casos de cálculo com
        a combinação, γn, peso próprio (D7) e detalhamento (φ, classe de agressividade,
        gancho).
     3. Método: classificação rígido ou flexível (NBR 6118:2023, 22.7.1), método da trilha de
        auditoria e a lista de premissas.
     4. Reações por estaca e caso.
     5. Verificações: descrição, solicitante, resistente, unidade, situação e referência
        normativa, com as não atendidas destacadas.
     6. Armaduras: identificação, tipo, força de cálculo, As necessária e referência.
     7. Alertas.
     8. Conferência por MEF (D14), só quando há `fem_result`: reações, verificações e alertas.
     9. Trilha de auditoria: versão, método, parâmetros e o hash das entradas de cada análise.
  3. Só valem resultados atuais: antes de montar o memorial, o projeto passa por
     `analysis.refresh_project` (ADR-004). Sem `result` não há memorial: a tela pede para
     calcular antes.
  4. PDF pela própria Qt: a tela (`blococalc.app`) imprime o HTML com `QTextDocument` em
     `QPdfWriter`, A4 retrato, numerando as páginas. Botão "Gerar memorial (PDF)" e item no
     menu Arquivo, com diálogo para escolher onde salvar.
- Alternativas descartadas:
  - reportlab ou WeasyPrint: dependência nova sem ganho para tabelas simples; WeasyPrint ainda
    exige bibliotecas nativas no Windows.
  - Word (.docx): editável demais para um documento que registra um cálculo auditado.
  - Gerar o PDF direto em `report`: o subpacote passaria a depender de Qt, contra a regra de
    que só `app` conhece Qt (CLAUDE.md §2).
- Consequências: sem mudança de contrato e sem dependência nova. `blococalc.report` entra na
  regra de arquitetura como camada pura (não importa `fem`, `viz`, `persistence` nem `app`). O
  layout fica limitado ao HTML que o `QTextDocument` suporta; desenhos do bloco no memorial
  ficam para depois da visualização 3D.
