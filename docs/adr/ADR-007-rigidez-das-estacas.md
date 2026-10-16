# ADR-007 — Rigidez axial das estacas na entrada (schemas v5)

- Status: proposta
- Contexto: a D16 (docs/02-metodos.md §4.7) troca os apoios rígidos do MEF por molas axiais
  nas estacas. A rigidez de cada estaca vem do projeto geotécnico e precisa ficar salva no
  projeto `.bloco` (ADR-004) junto com as outras entradas, para o MEF ser refeito com os mesmos
  dados. `Pile` não tem onde guardar esse valor.
- Decisão: publicar `schemas` v5, lendo v1 a v4 sem perda.
  1. `Pile` ganha `axial_stiffness: float | None = None` (> 0, N/mm). `None` mantém a estaca
     rígida, que é o comportamento atual; arquivos antigos abrem com todas as estacas rígidas.
  2. O hash das entradas passa a ignorar campos `None`. Assim os arquivos v4 salvos continuam
     com os resultados válidos, e uma estaca com rigidez informada muda o hash como qualquer
     outra entrada.
  3. O valor só é usado pela conferência por MEF (D16). `analyze()` (M1 e M5) não muda e avisa
     quando as estacas têm rigidezes diferentes, porque o M1 supõe estacas iguais.
  4. Na tela, a tabela de estacas ganha a coluna "k [kN/mm]", vazia por padrão.
- Alternativas descartadas:
  - Uma rigidez única como opção do MEF, fora do projeto: não fica salva e não permite estacas
    de comprimentos diferentes.
  - Estimar `k` pelo programa (por exemplo `Ecs·A/L`): exige comprimento e tipo de estaca e
    ignora o solo; um valor que parece normativo sem ser seria um padrão inventado (CLAUDE.md
    §6). Fica só como texto de ajuda.
- Consequências: `SCHEMA_VERSION` passa a "5". Arquivos salvos pela versão nova não abrem em
  versões antigas (campo desconhecido), como em toda mudança de contrato.
