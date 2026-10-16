# ADR-004 — Arquivo de projeto (schemas v4)

- Status: proposta (aguarda aprovação de Rodrigo)
- Contexto: o app (`blococalc.app`) monta as entradas em tabelas, mas tudo se perde ao fechar a
  janela. Para uso real o projeto precisa ser salvo e reaberto com as entradas, o último
  resultado e a trilha de auditoria (CLAUDE.md §8), sem que um resultado antigo seja mostrado
  como se valesse para entradas ou versões do programa diferentes. `blococalc.schemas` não tem
  um contrato que agrupe as quatro entradas e os resultados, e a camada `persistence` está vazia.
- Decisão: publicar `schemas` v4, lendo v1, v2 e v3 sem perda.
  1. Novo contrato de topo `Project`:

     | Campo | Tipo | Conteúdo |
     |---|---|---|
     | `name` | `str` (não vazio) | Nome do bloco ou da obra, mostrado no título da janela |
     | `notes` | `str` | Observações livres do engenheiro, vazio por padrão |
     | `geometry` | `GeometryInput` | Entrada da análise |
     | `materials` | `MaterialsInput` | Entrada da análise |
     | `loads` | `LoadsInput` | Entrada da análise |
     | `detailing` | `DetailingInput` | Entrada da análise, com os valores padrão da ADR-002 |
     | `result` | `AnalysisResult \| None` | Último resultado de `analyze()` |
     | `fem_result` | `AnalysisResult \| None` | Último resultado de `fem_verification()` (D14) |

     Os resultados são cópias do que o motor devolveu; o arquivo não é fonte de cálculo.
  2. Formato em disco: JSON UTF-8 indentado (`Project.model_dump_json(indent=2)`), extensão
     `.bloco`. Unidades internas (N, mm, MPa), as mesmas do motor; a conversão para kN e kN·m
     continua só na tela.
  3. Resultado desatualizado: ao abrir, o resultado salvo só é aceito se o `audit.input_hash`
     dele for igual ao hash das entradas do próprio arquivo e o `audit.app_version` for igual ao
     do programa. Caso contrário o app descarta a cópia salva, recalcula `analyze()` (rápido) e
     avisa; o `fem_result` desatualizado é descartado com aviso, sem rodar o MEF de novo
     (minutos e exige o CalculiX). Assim a tela nunca mostra um resultado que não corresponde
     às entradas visíveis.
  4. Gravação atômica em `blococalc.persistence.project`: grava em arquivo temporário na mesma
     pasta e troca pelo definitivo (`os.replace`), para que uma queda ou a sincronização do
     OneDrive não deixem um projeto pela metade. Funções `save_project(path, project)` e
     `load_project(path) -> Project`; erros de leitura e de validação viram uma única exceção
     `ProjectFileError` com mensagem em português.
  5. Tela: menu Arquivo com Novo, Abrir, Salvar e Salvar como (atalhos padrão do Windows),
     título com o nome do projeto e `*` quando há alteração não salva, e pergunta ao fechar
     com alterações pendentes.
  6. `schema_version` passa a `"4"`; o validador aceita "1" a "4". Como o hash de entradas
     inclui a versão, resultados calculados antes da v4 deixam de bater, o que é o
     comportamento desejado (não havia arquivos salvos antes).
- Alternativas descartadas:
  - Salvar só as entradas e recalcular sempre: perde o resultado do MEF (caro) e a trilha de
    auditoria do momento em que o projeto foi entregue.
  - Vários projetos ou blocos num arquivo: fica para quando houver relatório de obra; um bloco
    por arquivo mantém o contrato simples.
  - Formato binário ou banco SQLite: não é legível nem comparável em revisão, sem ganho para
    arquivos de poucos kB.
  - Modelo do arquivo em `persistence` em vez de `schemas`: a tela e a persistência trocariam
    um tipo fora dos contratos, contra a regra de fronteira (CLAUDE.md §2).
- Consequências: a tela passa a importar `blococalc.persistence`; `core`, `standards` e
  `geometry` continuam sem I/O. Projetos recentes, exportação de relatório e vários blocos por
  obra ficam para depois. A mudança de versão é aditiva: arquivos v4 não são lidos por versões
  anteriores do programa.
