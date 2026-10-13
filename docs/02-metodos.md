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
| Faixas sobre as estacas | 22.7.2.1 a) | Trações concentradas nas linhas sobre as estacas, em faixas de largura 1,2·φ da estaca | Pinada |
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
| Superfícies críticas de punção | 19.5.1 | C na face do pilar (compressão diagonal); C′ a 2d da face (tração diagonal); C″ só com armadura de punção | Pinada |
| Tensão solicitante, pilar interno | 19.5.2.1 | `τSd = FSd/(u·d)`, `d = (dx + dy)/2`; `FSd` pode ser reduzida da força aplicada na face oposta dentro do contorno (no bloco: reações das estacas dentro de C′) | Pinada |
| Tensão solicitante com momento | 19.5.2.2 | `τSd = FSd/(u·d) + K·MSd/(Wp·d)`; K pela Tab. 19.2 (C1/C2 = 0,5 / 1,0 / 2,0 / 3,0 → 0,45 / 0,60 / 0,70 / 0,80; circular 0,6); pilar retangular `Wp = C1²/2 + C1·C2 + 4·C2·d + 16·d² + 2π·d·C1` | Pinada (interpolação linear na Tab. 19.2 e extremos constantes: premissa nossa) |
| Pilares de borda e de canto | 19.5.2.3, 19.5.2.4 | Perímetro reduzido u*; não usados no bloco enquanto C′ couber no bloco | Pinada (não implementada) |
| Tração diagonal em C′ sem armadura | 19.5.3.2 | `τRd1 = 0,13·ke·(100·ρ·fck)^(1/3) + 0,10·σcp`; `ke = 1 + √(20/d) ≤ 2` (d em cm); `ρ = √(ρx·ρy) ≤ 0,02`, taxas na largura do pilar + 3d para cada lado; σcp = 0 no bloco | Pinada |
| Armadura de punção | 19.5.3.3 | `sr ≤ 0,75d`; fywd ≤ 300 MPa (conectores) ou 250 MPa (estribos) | Pinada (não implementada) |
| Cisalhamento em laje sem estribos | 19.4.1 | `VSd ≤ VRd1 = [τRd·k·(1,2 + 40ρ1) + 0,15σcp]·bw·d`, com VSd a d da face do apoio; `τRd = 0,25·fctd`, limitado ao valor de fck = 60 MPa; `ρ1 = As1/(bw·d) ≤ 0,02`; `k = 1,6 − d ≥ 1` (d em m), ou 1 se 50 % da armadura inferior não chega ao apoio | Pinada |
| Flexão: hipóteses básicas | 17.2.2 e) | Retângulo de profundidade `λx` e tensão `αc·ηc·fcd`; λ = 0,8 (fck ≤ 50) ou 0,8 − (fck − 50)/400; αc = 0,85 (fck ≤ 50) ou 0,85·[1 − (fck − 50)/200]; ×0,9 se a largura diminuir para a borda comprimida | Pinada |
| ηc | 8.2.10.1 | ηc = 1,0 (fck ≤ 40 MPa) ou (40/fck)^(1/3) | Pinada |
| Dutilidade | 14.6.4.3 | `x/d ≤ 0,45` (fck ≤ 50 MPa) ou `≤ 0,35` (50 < fck ≤ 90) | Pinada |
| Armadura mínima de tração | 17.3.5.2.1 e 19.3.3.2 | `Md,mín = 0,8·W0·fctk,sup`, taxa absoluta ≥ 0,15 %; a 19.3.3.2 aceita esse critério em lajes | Pinada |
| Suspensão: mudança de edição | 22.7.4.1.3 | A edição 2014 usava espaçamento > 3φ; a 2023 usa > 3·h | Pinada |
| fcd | 12.3.3 | `fcd = fck/γc` (t ≥ 28 d) | Pinada |
| γc, γs | 12.4.1, Tab. 12.1 | Normais 1,4 / 1,15; especiais 1,2 / 1,15; excepcionais 1,2 / 1,0; γc × 1,1 em condições desfavoráveis | Pinada |
| Ganchos | 9.4.2.3, Tab. 9.1 | Semicircular (ponta 2φ), 45° (4φ), reto (8φ); pinos de dobramento CA-50: 5φ (< 20 mm), 8φ (≥ 20 mm) | Pinada |
| Ancoragem básica | 9.4.2.4 | `ℓb = (φ/4)·(fyd/fbd) ≥ 25φ` | Pinada |
| Ancoragem necessária | 9.4.2.5 | `ℓb,nec = α·ℓb·As,calc/As,ef ≥ ℓb,min`; α = 1,0 sem gancho, 0,7 com gancho e cobrimento ≥ 3φ; ℓb,min = máx(0,3ℓb; 10φ; 100 mm) | Pinada |
| fbd | 9.3.2.1, Tab. 8.2 | `fbd = η1·η2·η3·fctd`, `fctd = fctk,inf/γc`; η1 = 2,25 (CA-50), 1,0 (CA-25, CA-60); η2 = 1,0 boa aderência, 0,7 má; η3 = 1,0 (φ < 32 mm), (132 − φ)/100 (φ ≥ 32 mm) | Pinada |
| Situação de aderência | 9.3.1 | Boa: barra inclinada > 45°, ou horizontal com h < 60 cm e até 30 cm acima da face inferior, ou h ≥ 60 cm e pelo menos 30 cm abaixo da face superior | Pinada |
| fctm, fctk | 8.2.5 | `fctm = 0,3·fck^(2/3)` (fck ≤ 50 MPa); `fctm = 2,12·ln[1 + 0,1·(fck + 8)]` (fck > 50 MPa; a edição 2014 trazia 0,11·fck); `fctk,inf = 0,7·fctm`; `fctk,sup = 1,3·fctm` | Pinada |
| Cobrimento | 7.4.7, Tab. 7.2 | `cnom = cmín + Δc`, Δc = 10 mm (5 mm com controle rigoroso explicitado em projeto); elementos em contato com o solo: cnom = 30 mm (CAA I e II), 40 mm (III), 50 mm (IV); cnom ≥ φ da barra; pode reduzir 5 mm com concreto acima da classe mínima. NBR 6122:2019, 8.6.2 remete à 6118 | Pinada |
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
| M8 | Pilar fictício: `Aeq = ΣAi`, `Ieq = Σ(Ii + Ai·di²)`; retângulo equivalente por inércia | "Método do pilar fictício"; Macedo cap. 5 | Padrão para vários pilares (D10), por área equivalente; conferir com M7 |
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
   tensão fcd1. Recomendado e aprovado (D6). Com as origens das bielas nos centroides das partes do
   pilar voltadas para cada estaca e d′ = 50 mm, o B1 dá y = 87,3 mm, tg θ = 1,15 e tirantes de
   200,5 kN (x) e 159,5 kN (y); ver `tests/unit/test_strut_tie.py`.
2. `y = 0` (z = d): maior braço, menor armadura; contra a segurança.
3. `y` por espraiamento a 45° como em Macedo (2022), y = 75 mm no B1: valor sem justificativa
   mecânica clara.

**Outras lacunas a pinar junto:** definição de `Lproj` para pilar retangular (proposta: por
direção, coerente com D4) e de `d′` (proposta: cobrimento + φ/2 do tirante, medido da cabeça da
estaca).

## 4.2 Bloco flexível (especificação, D9 aprovada)

A NBR 6118:2023 não dá método fechado para o bloco flexível: pede análise completa (22.7.2.2) e os
requisitos de lajes e punção (22.7.4.2, Seções 19 e 20). A proposta combina as seções de
referência do CEB-FIP 70 (Boletim 73, Apêndice 4, tradução de Macedo 2023) com as verificações da
NBR 6118. Unidades N, mm, MPa.

| Etapa | Regra | Fonte |
|---|---|---|
| Reações | Distribuição linear (M1), mesma do bloco rígido | CEB-70 §2 |
| Altura útil | Barras em x na camada inferior: `dx = h − embutimento − (c + φ/2)`; `dy = dx − φ` | D8 estendida |
| Seção de flexão S1 | Plano a `0,15·ap` para dentro da face do pilar, em cada lado e direção; largura = bloco inteiro; `d ≤ 1,5·` distância de S1 ao eixo da estaca mais afastada | CEB-70 §3.1 |
| Momento em S1 | `Md = Σ Ri·(distância do eixo da estaca a S1)` das estacas do lado não cruzado pelo eixo do pilar; vale o maior dos dois lados | CEB-70 §3.2 |
| Armadura | Retângulo da 17.2.2 e); `x/d` acima do limite da 14.6.4.3 é falha (sem armadura dupla); As ≥ As,mín da 17.3.5.2.1 | NBR 6118:2023 |
| Armadura secundária | ≥ 20 % da principal em cada direção | CEB-70 §3.2 (1/5) |
| Cisalhamento | `VSd` = reações das estacas além da face do pilar (estaca cortada pela face entra com parcela linear); a 19.4.1 toma VSd a `d` da face, e contar inteiras as estacas entre a face e essa seção fica a favor da segurança, sem a redução a/2d; `bw` = largura do bloco; `VSd ≤ VRd1` com `As1` = armadura da direção; acima disso é falha (estribos fora do escopo) | NBR 6118:2023, 19.4.1 |
| Punção no pilar | Pilar interno com momento (19.5.2.2); C: `τSd ≤ τRd2` com `FSd` inteira; C′ a 2d: `τSd ≤ τRd1`, `FSd` menos as reações das estacas com eixo dentro de C′; se C′ sai do bloco, bloqueia com alerta | NBR 6118:2023, 19.5 |
| Estacas de canto e de borda | Punção e cisalhamento local ficam como alerta até o MEF | CEB-70 §6.4; NBR 19.5.2.3/4 |

## 4.3 Treliça 3D M7 (especificação proposta, D12 em análise)

Objetivo (D10): confrontar o pilar fictício com um modelo espacial de bielas e tirantes que
enxerga cada pilar real. Fonte: Gomes (2015), "Análise tridimensional automática de blocos de
coroamento", cap. 3.4 e 4 (pasta REFERENCIAS-BIBLIOGRAFIA). Unidades N, mm, MPa.

**Como a fonte faz.** Nós em dois planos: um nó por estaca no fundo e nós de carga no topo
(momento do pilar vira binário de forças verticais nos centros das metades da seção, §5.1.3).
Reações calculadas antes pelo estaqueamento (M1) e aplicadas como forças. O programa enumera todas
as treliças isostáticas (3n − 6 barras entre as C(n,2) ligações possíveis), descarta as que têm
nó com menos de três barras não coplanares, elementos sobrepostos, bielas que se cruzam fora dos
nós, ângulo biela-tirante fora dos limites ou tirante diagonal entre os planos, e escolhe a de
menor energia de deformação, `mín Σ Ft·lt` (eq. 3.7).

**Achados na fonte.**
- O vetor de energia implementado (eq. 4.51) soma só as forças dos tirantes, sem o comprimento,
  ao contrário da eq. 3.7 que o próprio texto deduz. Seguimos a eq. 3.7.
- A enumeração cresce como C(n(n−1)/2, 3n − 6): 455 modelos para 2 pilares e 4 estacas, mais de
  13 milhões para 2 pilares e 6 estacas. Não serve para o B6 (16 estacas, 3 pilares), que é
  justamente o caso que D10 precisa confrontar.

**Proposta (D12).**

| Etapa | Regra | Fonte |
|---|---|---|
| Nós de carga | Um nó por pilar real no centro; com momento, binário nos centros das metades da seção na direção do momento (quatro nós com momento nas duas direções); nó tracionado ganha tirante vertical obrigatório até o fundo | Gomes §4.1, §4.5, §5.1.3 |
| Planos | Topo a `y/2` abaixo da face superior, com `y` do M5 (D6) no mesmo caso; fundo no eixo do tirante (`d′`, D8). Assim o braço é o mesmo `z = d − y/2` do M5 e a comparação isola o efeito do pilar fictício | D6, D8 |
| Reações | M1, as mesmas do restante da análise, aplicadas como forças nos nós das estacas | Gomes §4.4 |
| Escolha do modelo | Mínimo de `Σ Ft·lt` sujeito ao equilíbrio de todos os nós, resolvido como programa linear sobre a estrutura de todas as ligações possíveis (ground structure); barras diagonais entre planos só podem ser bielas (Gomes §4.14). Dá o mesmo ótimo da enumeração quando ele é isostático e sem dependência do número de nós | Gomes eq. 3.7; Dorn, Gomory e Greenberg (1964) |
| Verificações depois do ótimo | Bielas que se cruzam fora dos nós e inclinação `0,57 ≤ tg θ ≤ 2` das bielas que chegam às estacas viram alerta; tensões nos nós dos pilares reais e das estacas pelas mesmas fórmulas do M5 | Gomes §4.12–4.13; NBR 6118:2023, 22.3.1 e 22.3.2 |
| Confronto com D10 | Para cada direção, compara a força de tração total no fundo do M7 (soma das projeções dos tirantes) com a do modelo de pilar fictício; se o fictício ficar abaixo do M7, alerta com a diferença percentual | D10 |
| Uso | Só comparação: o dimensionamento continua pelo pilar fictício até o MEF | D2, D10 |
| Validação | B5 (Gomes §5.1, 4 estacas, binário de 320 e 2820 kN): recalcular e conferir as forças da Tab. 5.2 no modelo equivalente; enumeração por força bruta nos casos pequenos (até 7 nós) confirma o ótimo do programa linear | B5 |

**Dependências novas:** `numpy` e `scipy` (programa linear `linprog`, método HiGHS), a registrar no
`pyproject.toml`. Ambos têm wheels para Windows e serão necessários também na fase do MEF.

## 5. Benchmarks propostos

Valores de referência serão **recalculados por nós** e conferidos contra a publicação. Diferenças
são registradas, nunca copiadas às cegas (ver B1).

| ID | Caso | Fonte | O que valida | Tolerância |
|---|---|---|---|---|
| B1 | Bloco 4 estacas, pilar 20×65, Fk = 700 kN, φ40, L = 120 cm, h = 100 cm, C35 | Macedo 2022, §6.1 (Tab. 6.1) | M3, M4, M5, M6 no mesmo caso | As < 2 % |
| B2 | Bloco 8 estacas, pilar 209×30, C35, φ60, h = 140 cm | Planilha "Bloco sobre N estacas" | M5 para N estacas, malha 20 %, armadura mínima | As < 2 % |
| B3 | 17 ensaios de Blévot & Frémy (4N2, 4N4, séries de 4 estacas) | Santos et al. 2019, Tab. 1 | Carga de ruptura prevista × ensaio, por método | Relatório de razão Fprev/Fensaio (não é teste de igualdade) |
| B4 | Exemplos de 5, 6, 7 e 16 estacas (simétricos e assimétricos) | CRSI Design Guide, cap. 8 | M1 (reações com momentos e estaqueamento assimétrico) | Reações < 1 % |
| B5 | Exemplo de validação do programa 3D | Gomes 2015, §5.1 | M7 e futura verificação MEF | Forças nas barras < 1 % (recalculadas) |
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
| D7 | Peso próprio do bloco = 5 % da força normal de cálculo de cada caso, no centro do bloco (NBR 6122:2019, 5.6 pede no mínimo 5 % da carga permanente; a normal de cálculo inclui variáveis, então fica a favor da segurança). Evita usar peso específico e γg, ainda não pinados | Aprovada (Rodrigo, 13/10/2026) |
| D8 | `d′` (cabeça da estaca ao eixo do tirante) = cobrimento + φ/2 do tirante | Aprovada (Rodrigo, 13/10/2026) |
| D9 | Bloco flexível: flexão nas seções S1 do CEB-70 com As pela NBR 6118 (17.2.2), cisalhamento 19.4.1 a d da face e punção no pilar 19.5 (C e C′), conforme §4.2; punção nas estacas de canto só alerta | Aprovada (Rodrigo, 13/10/2026) |
| D10 | Vários pilares: pilar fictício de área equivalente (área = soma das áreas, lados na razão √(Sx/Sy) do grupo, na resultante das normais de cada caso), com verificação do nó de cada pilar real; o resultado deve ser confrontado com o modelo de treliça 3D (M7) quando ele for implementado | Aprovada (Rodrigo, 13/10/2026) |
| D11 | Armadura de suspensão (22.7.4.1.3): sem método de cálculo na norma nem nas referências; o programa mantém o alerta e o item de área zero no resultado | Aprovada (Rodrigo, 13/10/2026) |
| D12 | Treliça 3D (M7) para confrontar D10: ótimo de `Σ Ft·lt` (Gomes eq. 3.7) por programa linear sobre todas as ligações, com planos e reações iguais aos do M5, verificações de cruzamento e inclinação depois do ótimo, e alerta quando o pilar fictício dá menos tração que o M7; adiciona numpy e scipy (§4.3) | Proposta (Claude); aguarda Rodrigo |

## 7. Ainda falta neste documento

- Completar as linhas **Pendente** (fbd, fctm, cobrimento, combinações).
- Fórmulas completas de M3–M5 para 2, 3 e 4 estacas, com unidades N, mm, MPa.
- Punção nas estacas de canto e de borda (perímetro reduzido) para blocos flexíveis.
