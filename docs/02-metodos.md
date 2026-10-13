# 02 — Métodos, cláusulas normativas e benchmarks

> Status: v0.2 (13/10/2026) — decisões 1 a 3 aprovadas pelo Rodrigo; decisões 4 e 5 com padrão
> provisório escolhido pelo Claude, abertas a revisão.
> Nenhuma fórmula daqui pode ser codificada antes de a linha correspondente estar marcada
> como **Pinada** e revisada. Linhas marcadas **Pendente** exigem conferência na fonte.
>
> As normas da ABNT são protegidas por direito autoral: este documento cita item, fórmula e
> paráfrase curta. Não copiar trechos longos das normas para o repositório.

## 0. Edições de referência

| Norma | Edição usada | Observação |
|---|---|---|
| ABNT NBR 6118 | 2023, versão corrigida 2 (30/01/2024) | Base de todo o motor |
| ABNT NBR 6122 | 2019 + Emenda 1:2022 | A "6122:2022" é a Emenda 1 (25/03/2022), de 2 páginas: altera só J.9, N.9, O.9 e P.9 (anexos de tipos de estaca). Os itens citados na seção 3 não mudaram |
| ABNT NBR 8681 | 2025 | Combinações e coeficientes de ponderação |
| ABNT NBR 6120 | 2019 | Cargas; não entra no motor v1 (cargas vêm do modelo global) |

## 1. Achados que mudam o escopo (decisão do Rodrigo)

1. **Critério rígido × flexível.** O escopo diz "distância do eixo do pilar ao centro da estaca mais
   afastada ≤ 2,0·d". **Esse critério não está na NBR 6118:2023.** O item 22.7.1 manda usar
   "critério análogo ao definido para sapatas", e o 22.6.1 define sapata rígida quando
   `h ≥ (a − ap)/3` nas duas direções. Para blocos, a interpretação usual é `a` = distância
   entre faces externas das estacas extremas (ou entre eixos, conforme autor) — **interpretação a
   decidir**. Os limites `0,5·h ≤ c ≤ 2·h` vêm do CEB-FIP Bulletin 73 (1970), que é outra coisa:
   faixa de validade do método das seções de referência. Macedo (2022, §4.4) ainda propõe um
   terceiro critério, pela inclinação da biela mais abatida (≥ ~35°, Blévot / Fusco).
   **Proposta:** o app calcula e mostra os três; o critério que governa é o da NBR 6118
   (22.6.1 por analogia), e os outros aparecem como alertas.
2. **Tensões-limite nas bielas.** A NBR 6118 (22.3.2) dá limites menores que os de Blévot
   (ex.: pilar de bloco de 4 estacas, Blévot ≈ 2,1·fcd contra fcd1 = 0,85·αv2·fcd ≈ 0,73·fcd para
   C35). Por isso o mercado migrou para Fusco (2013) e Santos/Stucchi (2013), que mudam a área
   de verificação (área ampliada) para usar os limites da norma. **Proposta:** método padrão do
   motor = Santos/Stucchi com limites da NBR 6118:2023; Blévot e Fusco como métodos
   comparativos, exibidos lado a lado, nunca como padrão.
3. **Coeficiente adicional γn = 1,2.** O item 22.2 (último parágrafo) exige γn ≥ 1,2 para
   consolos, dentes Gerber "e elementos que se comportam como tais". Vários autores (Macedo,
   planilha "Bloco sobre N estacas", nota do pilar fictício) aplicam 1,2 a blocos. **Proposta:**
   γn = 1,2 como padrão conservador, editável com registro na trilha de auditoria.

## 2. Mapa de cláusulas (NBR 6118:2023)

| Tema | Item | O que diz (paráfrase) | Status |
|---|---|---|---|
| Conceito de bloco; rígido/flexível | 22.7.1 → 22.6.1 | Rígido por analogia à sapata: `h ≥ (a − ap)/3` | Pinada (interpretação de `a` pendente) |
| Comportamento do bloco rígido | 22.7.2.1 | Tração concentrada em faixas sobre as estacas de largura 1,2·φ; transmissão por bielas; ruína por compressão das bielas, não por tração diagonal | Pinada |
| Bloco flexível | 22.7.2.2, 22.7.4.2 | Análise completa (reações, tirantes, cisalhamento, punção); requisitos de lajes (Seções 19 e 20) | Pinada |
| Modelos aceitos | 22.7.3 | Modelos 3D lineares/não lineares e biela-tirante 3D; fendilhamento no contato pilar–bloco conforme 21.2; interação solo-estrutura se houver força horizontal significativa ou forte assimetria | Pinada |
| Armadura de flexão (tirantes) | 22.7.4.1.1 | > 85 % nas faixas sobre as estacas; barras de face a face com gancho; ancoragem medida a partir da face interna da estaca; estaca tracionada ancorada no topo do bloco (Fig. 22.7) | Pinada |
| Armadura de distribuição | 22.7.4.1.2 | Malha positiva adicional nas duas direções = 20 % do total das forças de tração em cada direção | Pinada |
| Armadura de suspensão | 22.7.4.1.3 | Obrigatória se a distribuição passar de 25 % dos esforços totais ou se espaçamento entre estacas > 3·h | Pinada |
| Arranque dos pilares | 22.7.4.1.4 | Altura suficiente para ancorar o arranque | Pinada |
| Armadura lateral e superior | 22.7.4.1.5 | Obrigatória em blocos com 2+ estacas em uma única linha | Pinada |
| Método de bielas e tirantes | 22.3.1 | Treliça isostática; reações de apoio obtidas antes; tg θ entre 0,57 e 2 (≈ 29,7° a 63,4°) | Pinada |
| Resistência de bielas e nós | 22.3.2 | `fcd1 = 0,85·αv2·fcd` (bielas prismáticas, nós CCC); `fcd2 = 0,60·αv2·fcd` (bielas cruzadas por mais de um tirante, nós CTT/TTT); `fcd3 = 0,72·αv2·fcd` (biela cruzada por tirante único, nós CCT) | Pinada |
| αv2 | 17.4.2.2 / 19.5.3.1 | `αv2 = 1 − fck/250`, fck em MPa | Pinada |
| Tirante | 22.3.3 | `As = FSd / fyd` | Pinada |
| Pressão de contato (pilar–bloco, estaca–bloco) | 21.2.1 | `FRd = Ac0·fcd·√(Ac1/Ac0) ≤ 3,3·fcd·Ac0`; Ac1 homotética a Ac0, lados na razão ≤ 2 | Pinada |
| Compressão diagonal no contorno C | 19.5.3.1 | `τSd ≤ τRd2 = 0,27·αv·fcd` (pode +20 % em pilar interno sob condições) | Pinada |
| Punção (bloco flexível) | 19.5.2, 19.5.3.2/3 | Contornos C, C′, C″ | Pendente (detalhar na fase de flexíveis) |
| fcd | 12.3.3 | `fcd = fck/γc` (t ≥ 28 d) | Pinada |
| γc, γs | 12.4.1, Tab. 12.1 | Normais 1,4 / 1,15; especiais 1,2 / 1,15; excepcionais 1,2 / 1,0; γc × 1,1 em condições desfavoráveis | Pinada |
| Ganchos | 9.4.2.3, Tab. 9.1 | Semicircular (ponta 2φ), 45° (4φ), reto (8φ); pinos de dobramento CA-50: 5φ (< 20 mm), 8φ (≥ 20 mm) | Pinada |
| Ancoragem básica | 9.4.2.4 | `ℓb = (φ/4)·(fyd/fbd) ≥ 25φ` | Pinada |
| Ancoragem necessária | 9.4.2.5 | `ℓb,nec = α·ℓb·As,calc/As,ef ≥ ℓb,min`; α = 1,0 sem gancho, 0,7 com gancho e cobrimento ≥ 3φ; ℓb,min = máx(0,3ℓb; 10φ; 100 mm) | Pinada |
| fbd | 9.3.2.1 | `fbd = η1·η2·η3·fctd` | Pendente (copiar η da norma na revisão) |
| fctm, fctk | 8.2.5 | Resistência à tração | Pendente |
| Cobrimento | 7.4.7, Tab. 7.2 | Por classe de agressividade | Pendente |
| Combinações | 11.8.2 (6118) + NBR 8681:2025 §5.1.4 | γf, ψ0 | Pendente |

## 3. Mapa de cláusulas (NBR 6122:2019, Em1:2022)

| Tema | Item | O que diz (paráfrase) | Status |
|---|---|---|---|
| Peso próprio do bloco | 5.6 | Considerar o peso próprio do bloco ou, no mínimo, 5 % da carga vertical permanente | Pinada |
| Cabeça da estaca e ligação | 8.5.5 | Lastro de concreto magro ≥ 5 cm; cabeça da estaca ≥ 5 cm acima do lastro; ligação especificada em projeto | Pinada |
| Excentricidade executiva | 8.5.6.1 / 8.5.6.2 | Estacas alinhadas: projetar para os momentos das excentricidades estimadas; reavaliar se > 10 % da menor dimensão. Estacas não alinhadas: aceita-se até +10 % na carga axial de cálculo sem correção | Pinada |
| Desaprumo | 8.5.7 | Revisar se o desvio for > 1:100 | Pinada |
| Bloco: dimensões mínimas | 7.x (fundação rasa) | Não se aplica a bloco sobre estacas | — |

## 4. Catálogo de métodos

| # | Método | Fonte na pasta | Uso no app (proposta) |
|---|---|---|---|
| M1 | Reações por equilíbrio estático de bloco rígido: `Ri = N/n ± My·xi/Σx² ± Mx·yi/Σy²` (eixos principais do estaqueamento) | Clássico; CRSI Design Guide cap. 8 | Padrão para blocos rígidos |
| M2 | Reações por análise elástica (grelha ou casca sobre molas) | Macedo §4.4, CEB-70 | Blocos flexíveis (fase posterior) |
| M3 | Blévot & Frémy (1967) — bielas e tirantes clássico, 2/3/4 estacas | Macedo §4.1 e §6.1.1; Santos et al. 2019 | Comparativo |
| M4 | Fusco (2013) — área ampliada no pilar (Tab. 4.2 x/b por taxa de armadura) e 1,4φ na estaca; limites 0,20·fcd e 0,25·fck | Macedo §4.3 e §6.1.2 | Comparativo |
| M5 | Santos/Stucchi (2013) — espraiamento a 45°, área ampliada, limites fcd1/fcd3 da NBR 6118 | Santos, Carvalho, Stucchi 2019; Macedo §6.1.4; planilha "Bloco sobre N estacas" | **Padrão** do motor |
| M6 | CEB-FIP 70 — seções de referência S1 (0,15·ap da face), S2; `As = Md/(0,85·d·fyd)`; `Vd,lim = 0,25·(1 − c/5d)·(b + d)·d·√fcd` | CEB FIP 70 (tradução); Macedo §4.4 e §6.1.3 | Blocos flexíveis e > 6 estacas (comparativo) |
| M7 | Bielas e tirantes 3D genérico por treliça (rigidez, energia mínima, cruzamento de bielas) | Gomes 2015 (UFRJ) cap. 4; van de Graaf 2006 | Layouts livres (fase posterior) |
| M8 | Pilar fictício: `Aeq = ΣAi`, `Ieq = Σ(Ii + Ai·di²)`; retângulo equivalente por inércia | "Método do pilar fictício"; Macedo cap. 5 | Múltiplos pilares (fase posterior) |
| M9 | Armadura de pele por efeito térmico | Araújo, "Armadura de pele para blocos" | Blocos de grande volume (alerta) |

## 4.1 Método padrão M5 — Santos/Stucchi (especificação; D6 aprovada)

Fonte: Santos, Carvalho e Stucchi (2019), §3.4, eq. (19) a (21) e Figuras 8 a 10.

| Grandeza | Expressão | Observação |
|---|---|---|
| Esforço de cálculo | `Nd = γn · Fd` (γn = 1,2, D3) | `Fd` já majorado por γf |
| Braço de alavanca | `z = d − 0,5·y` | `y` = profundidade do nó CCC sob o pilar |
| Inclinação da biela | `tg θ = z / Lproj` | `Lproj` = projeção horizontal da biela até o eixo da estaca |
| Área ampliada no pilar | `Ac,sp = (ac + 2y)·(bc + 2y)` | espraiamento a 45° (Fig. 8) |
| Tensão no nó do pilar (CCC) | `σcd,c = Nd / (Ac,sp · sen²θ) ≤ fcd1` | eq. (20); NBR 6118:2023, 22.3.2 |
| Área ampliada na estaca | `Ap,sp = π·(φ + 2d′)²/4` (circular) ou `(a + 2d′)²` (quadrada) | `d′` = distância da cabeça da estaca ao eixo do tirante |
| Tensão no nó da estaca (CCT) | `σcd,p = Rd / (Ap,sp · sen²θ) ≤ fcd3` | eq. (19); NBR 6118:2023, 22.3.2 |
| Ductilidade | `y/d ≤ 0,3` | recomendação dos autores (§3.5) |
| Tirante | `Ftd = Rd · cotg θ` na direção da biela, decomposto nas faixas sobre as estacas; `As = Ftd/fyd` | NBR 6118:2023, 22.3.3 e 22.7.4.1.1 |
| Inclinação | `0,57 ≤ tg θ ≤ 2`; autores recomendam θ ≥ 45° | NBR 6118:2023, 22.3.1 |

**Lacuna encontrada (decisão D6).** O procedimento manda iterar `y` até `σcd,c = fcd1`. No B1
(Nd = 1176 kN, pilar 20×65, C35), `σcd,c` já é 15,8 MPa com `y = 0`, abaixo de fcd1 = 18,27 MPa:
a iteração não tem raiz e `y` fica indefinido. Opções:

1. `y` pelo equilíbrio horizontal do nó CCC (analogia com a flexão, que os próprios autores
   citam): a compressão horizontal que equilibra os tirantes atua numa faixa de altura `y` sob
   tensão fcd1. No B1 dá y = 31 mm, θ = 48,7°, Ftd = 258,5 kN por diagonal. Recomendado.
2. `y = 0` (z = d): maior braço, menor armadura; contra a segurança.
3. `y` por espraiamento a 45° como em Macedo (2022), y = 75 mm no B1: valor sem justificativa
   mecânica clara.

**Outras lacunas a pinar junto:** definição de `Lproj` para pilar retangular (proposta: por
direção, coerente com D4) e de `d′` (proposta: cobrimento + φ/2 do tirante, medido da cabeça da
estaca).

## 5. Benchmarks propostos

Valores de referência serão **recalculados por nós** e conferidos contra a publicação. Diferenças
são registradas, nunca copiadas às cegas (ver B1).

| ID | Caso | Fonte | O que valida | Tolerância |
|---|---|---|---|---|
| B1 | Bloco 4 estacas, pilar 20×65, Fk = 700 kN, φ40, L = 120 cm, h = 100 cm, C35 | Macedo 2022, §6.1 (Tab. 6.1) | M3, M4, M5, M6 no mesmo caso | As < 2 % |
| B2 | Bloco 8 estacas, pilar 209×30, C35, φ60, h = 140 cm | Planilha "Bloco sobre N estacas" | M5 para N estacas, malha 20 %, armadura mínima | As < 2 % |
| B3 | 17 ensaios de Blévot & Frémy (4N2, 4N4, séries de 4 estacas) | Santos et al. 2019, Tab. 1 | Carga de ruptura prevista × ensaio, por método | Relatório de razão Fprev/Fensaio (não é teste de igualdade) |
| B4 | Exemplos de 5, 6, 7 e 16 estacas (simétricos e assimétricos) | CRSI Design Guide, cap. 8 | M1 (reações com momentos e estaqueamento assimétrico) | Reações < 1 % |
| B5 | Exemplo de validação do programa 3D | Gomes 2015, §5.1 | M7 e futura verificação MEF | A definir |
| B6 | Bloco com 16 estacas e 3 pilares | Macedo 2022, §6.2 | M8 (múltiplos pilares) | A definir |

**Problemas já encontrados em B1** (por isso recalculamos):
- Blévot: Macedo usa θ = 52° medido no CAD; pela geometria do modelo, `tg θ = d / (L√2/2 − ap√2/4)` dá θ = 49,2°. A força no tirante (254,09 kN) e As (5,84 cm²) conferem.
- Santos: o texto diz d = 81,6 cm, mas a conta usa 82,5 cm (= 100 − 10 − 7,5, que é o correto para x = 7,5). T = 277,19 kN confere com 82,5.
- Santos: σlim na estaca escrito como 16,13 MPa; `0,72 × 0,86 × 25` = 15,48 MPa.
- Pilar retangular 20×65 no modelo de Blévot (concebido para pilar quadrado): Macedo usa ap = 20 cm. Precisamos decidir a regra (lado menor, pilar quadrado equivalente, ou modelo por direção).

## 6. Decisões

| # | Decisão | Situação |
|---|---|---|
| D1 | Critério rígido × flexível: governa NBR 6118 22.7.1 → 22.6.1; CEB-70 (0,5h–2h) e ângulo mínimo da biela (~35°) viram alertas | Aprovada (Rodrigo, 13/10/2026) |
| D2 | Método padrão = Santos/Stucchi com limites fcd1/fcd3 da NBR 6118; Blévot e Fusco só comparativos | Aprovada (Rodrigo, 13/10/2026) |
| D3 | γn = 1,2 padrão para blocos, editável com registro na trilha de auditoria | Aprovada (Rodrigo, 13/10/2026) |
| D4 | Pilar retangular nos modelos de bielas: o modelo é montado por direção, usando a dimensão do pilar naquela direção (ap em x, bp em y); nunca o lado menor para as duas | Padrão provisório (Claude); revisar |
| D5 | `a` no critério `h ≥ (a − ap)/3`: dimensão do bloco na direção considerada (analogia literal com a sapata, e mais conservadora que usar a distância entre eixos) | Padrão provisório (Claude); revisar |
| D6 | Profundidade `y` do nó CCC (Santos/Stucchi): equilíbrio horizontal do nó, com a compressão horizontal que equilibra os tirantes atuando sob fcd1 numa faixa de altura `y` (ver §4.1) | Aprovada (Rodrigo, 13/10/2026) |

## 7. Ainda falta neste documento

- Completar as linhas **Pendente** (fbd, fctm, cobrimento, combinações).
- Fórmulas completas de M3–M5 para 2, 3 e 4 estacas, com unidades N, mm, MPa.
- Punção e cisalhamento para blocos flexíveis (fase posterior).
