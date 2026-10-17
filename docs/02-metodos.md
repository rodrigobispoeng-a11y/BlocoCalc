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
| Espaçamento livre entre barras | 18.3.2.2 | Horizontal `ah ≥ máx(20 mm; φ; 1,2·dmáx)`; vertical `av ≥ máx(20 mm; φ; 0,5·dmáx)`; dmáx = dimensão máxima característica do agregado graúdo; feixes pelo diâmetro equivalente | Proposta (D18) |
| Lajes: prescrições gerais | 20.1 | φ ≤ h/8; armadura principal com espaçamento ≤ mín(2h; 20 cm) na região dos maiores momentos, ou ≤ 15φ para φ ≥ 20 mm; secundária ≥ 20 % da principal com espaçamento ≤ 33 cm | Proposta (D18) |
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
   pilar voltadas para cada estaca e d′ = 50 mm, o B1 dá y = 55,2 mm, tg θ = 1,17 e tirantes de
   196,6 kN (x) e 156,4 kN (y), com a face do nó espraiada a 45° (D13; antes 87,3 mm, 200,5 e
   159,5 kN); ver `tests/unit/test_strut_tie.py`.
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

## 4.3 Treliça 3D M7 (especificação, D12 aprovada)

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

**Especificação (D12).**

| Etapa | Regra | Fonte |
|---|---|---|
| Nós de carga | Quatro nós por pilar real, nos centros dos quadrantes da seção (±bx/4, ±by/4), com `N/4 ± My/bx ± Mx/by` (H entra como momento com o braço do M1); são as origens das bielas do M5, de modo que com um só pilar as trações do M7 e do M5 coincidem (teste golden no B1). Nó tracionado ganha tirante vertical até o fundo, e estaca tracionada até o topo | Gomes §4.1, §4.5, §5.1.3; D6 |
| Peso próprio | D7 em cada pilar (5 % da sua normal), com as reações M1 recalculadas assim, para o equilíbrio dos nós | D7 |
| Planos | Topo a `y/2` abaixo da face superior, com `y` do M5 (D6) no mesmo caso; fundo no eixo do tirante (`d′`, D8). Assim o braço é o mesmo `z = d − y/2` do M5 e a comparação isola o efeito do pilar fictício | D6, D8 |
| Reações | M1, as mesmas do restante da análise, aplicadas como forças nos nós das estacas | Gomes §4.4 |
| Escolha do modelo | Mínimo de `Σ Ft·lt` sujeito ao equilíbrio de todos os nós, resolvido como programa linear sobre a estrutura de todas as ligações possíveis (ground structure); barras diagonais entre planos só podem ser bielas (Gomes §4.14). Dá o mesmo ótimo da enumeração quando ele é isostático e sem dependência do número de nós | Gomes eq. 3.7; Dorn, Gomory e Greenberg (1964) |
| Verificações depois do ótimo | Bielas que se cruzam fora dos nós e inclinação `0,57 ≤ tg θ ≤ 2` das bielas que chegam às estacas viram alerta; tensões nos nós dos pilares reais e das estacas pelas mesmas fórmulas do M5 | Gomes §4.12–4.13; NBR 6118:2023, 22.3.1 e 22.3.2 |
| Confronto com D10 | Para cada direção, compara a força de tração total no fundo do M7 (soma das projeções dos tirantes) com a do modelo de pilar fictício; se o fictício ficar abaixo do M7, alerta com a diferença percentual | D10 |
| Uso | Só comparação: o dimensionamento continua pelo pilar fictício até o MEF | D2, D10 |
| Validação | B5 (Gomes §5.1, 4 estacas, binário de 320 e 2820 kN): recalcular e conferir as forças da Tab. 5.2 no modelo equivalente; enumeração por força bruta nos casos pequenos (até 7 nós) confirma o ótimo do programa linear | B5 |

**B5 recalculado.** Com as reações exatas (3140/4 ± 500/3 kN), o modelo da Fig. 5.3 dá B1 = −279,3,
B2 = −968,7, B3 = −1661,3, B4 = −270,8, T1 = 713,5, T2 = 1098,1 e T3 = 805,3 kN, iguais à Tab. 5.2
a menos de 0,2 kN (arredondamento). O programa linear sobre as 15 ligações possíveis reproduz
exatamente as mesmas bielas e a mesma energia `Σ Ft·lt` = 5133 kN·m, mas o ótimo não é único: troca
parte de T1 e T3 por tirantes nas diagonais do fundo. As somas das projeções dos tirantes em x e em
y são as mesmas nos dois arranjos, por isso o confronto com D10 usa essas somas. Para o arranjo
impresso ser o construtivo, a proposta inclui um desempate: tirantes fora das direções x e y pesam
0,1 % a mais.

**Dependências novas:** `numpy` e `scipy` (programa linear `linprog`, método HiGHS), a registrar no
`pyproject.toml`. Ambos têm wheels para Windows e serão necessários também na fase do MEF.

## 4.4 M5 para N estacas (especificação, D13 aprovada)

Objetivo: levar o M5 (e com ele o pilar fictício, D10, e o confronto com o M7, D12) a blocos com 5
ou mais estacas. Fonte: planilha "Bloco Sobre N estacas" (Mathcad, Macedo), que é o B2: bloco
540×240×140 cm, 8 estacas φ60 em 4 linhas em x e 2 em y, pilar 209×30, C35, CA-50, cobrimento 5 cm,
φ25 no tirante, reação de 113,96 tf na estaca mais solicitada.

**Como a fonte faz.** Uma biela por estaca, do pilar até a estaca mais solicitada, com
`Td = R·γf·γn·a/z` e `Tdx = Td·cos α`, `Tdy = Td·cos β`; `As` = maior entre esse valor e a
armadura mínima. A profundidade comprimida `x` sai da tensão vertical sob o pilar ampliado a 45°
(15,04 cm) e o braço é medido até a cabeça da estaca, `z = h − emb − x/2`.

**Achados na fonte.**
- `a = 161,4 cm` e `α = 24,719°` foram "medidos". Com as estacas espaçadas de 150 cm (2,5φ, 45 cm
  da borda, o que fecha 540×240) e o pilar dividido em 4×2 partes iguais, a biela da estaca de
  canto sai do centroide da parte correspondente e dá exatamente 161,4 cm e 24,719°. É a mesma
  regra do M5 (centroide da parte do pilar voltada para a estaca), em grade.
- O tirante por estaca não equilibra a linha de estacas. Numa linha com 4 estacas, o trecho
  central recebe a componente horizontal da estaca de canto **mais** a da estaca interna. No B2
  o trecho central pede 33 % mais que o de canto. A treliça M7 com os mesmos nós confirma o valor
  acumulado (soma das trações igual a 1e-6).
- `Fzk_pil` é calculado como 8 × 113,96 = 911,68 tf e depois sobrescrito por 435,97 tf, usado só
  na profundidade `x`. Os dois valores não são compatíveis com reação igual nas 8 estacas.
- Com D6 como está (compressão horizontal atravessando uma face da largura do pilar), o B2 não tem
  solução: o pilar-parede de 30 cm não equilibra a compressão em x e `y` passa de `d`.

**Especificação (D13).**

| Etapa | Regra | Fonte |
|---|---|---|
| Escopo | Estacas em grade retangular completa, nx × ny (nx, ny ≥ 1, nx·ny ≥ 5), todas comprimidas, um pilar (vários pilares pelo pilar fictício, D10). 2 a 4 estacas seguem a §4.1. Outros arranjos (5 em quincôncio, hexágono) continuam bloqueados com aviso | planilha N estacas |
| Origem das bielas | Pilar dividido em nx × ny partes iguais; a biela de cada estaca sai do centroide da parte de mesma linha e coluna. Para 2×2 dá os quadrantes da §4.1. Estaca sob o centroide da sua parte vira biela vertical: sem tirante e sem limite de inclinação, com o nó verificado com sen²θ = 1 | D6; planilha N estacas |
| Profundidade `y` | Equilíbrio horizontal do nó (D6), com a face espraiada a 45°: largura `by + 2y` para a compressão em x e `bx + 2y` em y, coerente com a área ampliada `(ac + 2y)(bc + 2y)` da eq. (20). Vale para todos os blocos, inclusive 2 a 4 estacas (opção 1 abaixo) | D6 (revisão pela D13) |
| Tirantes | Um tirante por linha de estacas em x e por coluna em y, com trechos entre estacas vizinhas. Força em cada trecho por equilíbrio dos nós: a maior entre a soma das componentes horizontais das estacas de um lado e a do outro. `As = Ftd/fyd` por trecho, faixa sobre as estacas | NBR 6118:2023, 22.3.3 e 22.7.4.1.1 |
| Detalhamento | Trechos alinhados de uma linha formam uma barra contínua com a armadura do trecho mais carregado; ancoragem verificada só nas estacas das pontas; a malha de 20 % (22.7.4.1.2) soma o trecho mais carregado de cada linha | NBR 6118:2023, 22.7.4.1.1 e 22.7.4.1.2 |
| Demais verificações | Iguais às da §4.1 (fcd1, fcd3, `0,57 ≤ tg θ ≤ 2`, `y/d ≤ 0,3`), por estaca | NBR 6118:2023, 22.3.1 e 22.3.2 |
| Validação | B2 recalculado (abaixo); M7 com um nó por parte do pilar reproduz a soma das trações em cada direção; propriedade de equilíbrio e simetria em grades 2×3, 3×3 e 4×4 | B2, B5 |

**Opções para a face do nó.** O Rodrigo escolheu a opção 1 em 13/10/2026.

| Opção | Regra | B1 (4 estacas, aprovado) | B2 |
|---|---|---|---|
| 1 (recomendada) | Face espraiada a 45° em todos os blocos | `y` 87,3 → 55,2 mm; tirante em x 200,5 → 196,6 kN (−2 %); golden do B1 atualizado com esta justificativa | `y` = 368,0 mm (`y/d` = 0,297), `z` = 1053,5 mm |
| 2 | Face espraiada só em blocos com 5 ou mais estacas | Inalterado | Igual à opção 1; o mesmo bloco muda de regra ao passar de 4 para 5 estacas |
| 3 | Face igual à largura do bloco (analogia com a flexão) | `y` 87,3 → 10,5 mm; tirante em x 200,5 → 191,4 kN (−4,5 %) | `y` = 143,6 mm, próximo dos 150,4 mm da fonte |

**B6 com a D13.** Pela figura, as 12 estacas formam uma grade 4×3 e o bloco passa pela análise
completa (`tests/benchmark/test_large_caps.py`). Com as cargas de 1100, 900 e 200 kN × 1,4, o
pilar fictício dá 2299 kN de tração em x e 1765 kN em y, contra 838 e 474 kN da treliça M7: fica
do lado seguro, como D10 exige. A soma das armaduras do pilar fictício em x (≈ 22 cm²) fica longe
dos 75,6 cm² do texto, que usa outra geometria (200×200 cm, 16 estacas); sem dados consistentes, o
B6 não vira teste de igualdade.

**B2 recalculado (opção 1).** d′ = 50 + 12,5 = 62,5 mm (D8), d = 1400 − 100 − 62,5 = 1237,5 mm,
Rd = 1,4 × 1,2 × 113,96 tf = 1877,4 kN em todas as estacas, fcd1 = 18,28 MPa.

| Grandeza | Fonte | Recalculado | Diferença |
|---|---|---|---|
| Lproj e α da estaca de canto | 161,4 cm; 24,719° | 161,42 cm; 24,719° | confere |
| tg θ, canto / interna | 0,759 / — | 0,653 / 1,264 | braço até o tirante (D8) e `y` por D6 |
| Tirante em x, trecho de canto | 2247,4 kN (51,69 cm²) | 2613,1 kN (60,10 cm²) | braço menor |
| Tirante em x, trecho central | não calcula | 3484,2 kN (80,14 cm²) | equilíbrio da linha |
| Tirante em y | 1034,6 kN (23,80 cm²) | 1203,0 kN (27,67 cm²) | braço menor |

Como a fonte usa outro braço e não equilibra a linha, o B2 não é teste de igualdade com a
publicação: os goldens são os valores recalculados, e a geometria das bielas (Lproj, α) confere
com a fonte a 0,1 %.

## 4.5 Verificação por MEF (especificação, D14 aprovada)

Objetivo: conferir por elementos finitos o modelo de bielas e tirantes (M5) dos blocos rígidos,
como o M7 confere o pilar fictício. O dimensionamento continua pelo M5; o MEF gera verificações
de comparação e alertas. Fontes: Macedo (2022), cap. 7 (ANSYS, análise linear com o maciço sem
armadura, cargas como tensões nos pilares, estacas como apoios distribuídos na área da estaca);
Bavaresco (2016), cap. 3 (SAP2000, análise linear, tração no fundo integrada em cortes verticais).

**Especificação (D14).**

| Etapa | Regra | Fonte |
|---|---|---|
| Modelo | Sólido do bloco (lx × ly × h), elástico linear, sem armadura; tetraedros quadráticos (C3D10) gerados pelo gmsh e resolvidos pelo CalculiX | Macedo §7.1; Bavaresco §3 |
| Material | `Ecs = αi·Eci`, `Eci = αE·5600·√fck` (fck ≤ 50 MPa), `αi = 0,8 + 0,2·fck/80 ≤ 1,0`, αE = 1,0 (granito e gnaisse) por padrão; ν = 0,2. Com apoios rígidos as tensões não dependem de E | NBR 6118:2023, 8.2.8 e 8.2.9 |
| Malha | Tamanho máximo = menor entre lx, ly e h dividido por 10 (100 mm no B1) | convergência no B1, abaixo |
| Apoios | Deslocamento vertical nulo em toda a área da cabeça de cada estaca, no plano do fundo do bloco (o embutimento não é modelado); restrição horizontal isostática (3 graus de liberdade), para as estacas não absorverem a tração dos tirantes. Mesma hipótese de estacas rígidas do M1 | M1; Macedo §7.1 |
| Cargas | Em cada pilar real, γn·(1 + D7)·Nd como pressão na área do pilar, com os momentos em distribuição linear (Navier) e H como tração tangencial uniforme | D3, D7; Macedo §7.1 |
| Validade do modelo | Reações do MEF contra as do M1 em cada estaca: diferença acima de 1 % invalida a comparação (aviso) | M1 |
| Tirantes | Em cada plano vertical a meio caminho entre duas linhas de estacas vizinhas, resultante das tensões normais de tração no plano, comparada com a soma das forças dos tirantes do M5 que cruzam o mesmo plano. Alerta quando o MEF passa o M5 em mais de 10 % | Bavaresco §3.4 |
| Nós | Média da tensão principal de compressão no volume do nó CCC (área do pilar × profundidade `y` do M5) contra fcd1, e no cilindro sobre cada estaca (área da estaca × 2·d′) contra fcd3. Alerta quando a média passa o limite; os picos da análise linear (cantos do pilar e borda da estaca) não são usados | NBR 6118:2023, 22.3.2 |
| Uso | Chamada separada, sob demanda (dezenas de segundos por caso), sem entrar em `analyze()`; o resultado traz o tamanho da malha e o número de nós na trilha de auditoria | D2 |
| Fora do escopo agora | Punção nas estacas de canto dos blocos flexíveis, análise não linear e armadura modelada | — |

**Protótipo no B1** (pilar 20×65, Nd·γn = 1176 kN, sem peso próprio, d′ = 50 mm):

| Grandeza | M1/M5 | MEF (malha 100 mm, 30 614 nós, 30 s) | Diferença |
|---|---|---|---|
| Reações | 294,0 kN | 293,7 a 294,1 kN | < 0,2 % |
| Tração no plano x = 0 | 393,2 kN (2 × 196,6) | 412,4 kN | +4,9 % |
| Tração no plano y = 0 | 312,8 kN (2 × 156,4) | 331,7 kN | +6,0 % |
| Tensão média no nó do pilar | 8,62 MPa (eq. 20) | 8,17 MPa | −5 % |
| Tensão média no nó da estaca | 2,59 MPa (eq. 19) | 1,59 MPa | −39 % |

A tração converge com a malha (412,3, 412,4 e 414,5 kN com 150, 100 e 70 mm); a malha de 70 mm
leva quase 4 min e não muda a resposta. O braço elástico (738 mm entre as resultantes) é menor
que o `z` do M5 (822 mm), daí os 5 a 6 % a mais de tração; por isso o alerta proposto é de 10 %.

**Dependências novas:** `gmsh` (pip, com wheels para Windows; licença GPL com exceções, a avaliar
antes de distribuir o programa) e o executável do CalculiX (`ccx`, GPL, chamado como processo
externo; no Windows vem com o PrePoMax ou o pacote bConverged, e o caminho fica configurável).
No CI, o Ubuntu instala `calculix-ccx`; os testes do MEF ficam marcados e só rodam onde o `ccx`
existe.

## 4.6 M5 para estacas fora de grade (especificação, D15 aprovada)

Objetivo: levar o M5 a blocos de um pilar com estacas no contorno de um polígono convexo
(pentágono, hexágono, quincôncio com a estaca central sob o pilar, hexágono com estaca central),
que hoje são recusados com aviso. Fonte principal: Bavaresco (2016), cap. 2 a 5: bloco B05P01,
420×420×210 cm, 4 estacas 60×60 nos vértices de um quadrado de 320 cm e uma no centro, pilar
100×100, Nd = 10 000 kN, C25, analisado pela regra dos 4/5 de Blévot e Frémy e por MEF linear
(SAP2000).

**O que a fonte mostra.**
- Regra clássica (Blévot e Frémy): o quincôncio é calculado como o bloco de 4 estacas com 4/5
  da carga; a estaca central recebe 1/5 direto do pilar.
- No MEF, a tração no fundo aparece nos dois caminhos: entre as estacas do contorno (≈ 1,5 MPa)
  e nas diagonais, com o pico junto à estaca central (≈ 2 MPa). Armar só pelos lados ou só pelas
  diagonais deixa uma das regiões só com a malha de 20 %. A fonte conclui que a regra dos 4/5 dá
  a quantidade certa de aço (89,5 cm² entre 78,8 e 94,3 cm² do MEF) desde que metade vá para os
  lados e metade para as diagonais.
- A estaca central recebeu 27,6 % da carga no MEF (estacas de 1 m engastadas), 39 % acima da
  média; a fonte recomenda folga de 40 % na verificação do nó dessa estaca.
- No nosso protótipo do mesmo bloco, a treliça M7 com as bielas do M5 escolhe o anel; mas, para
  polígonos regulares com empuxo radial, anel e tirantes radiais (diagonais) têm exatamente o
  mesmo Σ F·l, de modo que o ótimo é empatado e o desempate é arbitrário. O MEF da D14 com apoios
  rígidos põe 52 % da carga na estaca central, o que invalida a comparação MEF × M1 (alerta da
  D14) e confirma que essa reação depende da rigidez das estacas.

**Especificação (D15).**

| Etapa | Regra | Fonte |
|---|---|---|
| Escopo | Um pilar; estacas do contorno formando polígono convexo (3 ou mais, sem três alinhadas); estacas internas só se o eixo estiver dentro da seção do pilar. Grades retangulares seguem a D13. Fileiras desencontradas, estacas internas fora do pilar e estacas alinhadas no contorno continuam bloqueadas com aviso | Bavaresco §2.3 |
| Reações | M1, como hoje (estacas de mesma rigidez) | M1 |
| Estacas internas | Biela vertical a partir do próprio eixo (regra dos 4/5 generalizada), sem tirante e sem limite de inclinação; nó do pilar com a parte da área proporcional à reação | Blévot e Frémy; D13 |
| Estacas do contorno | Biela a partir do centroide da parte do pilar voltada para a estaca (regra atual de 2 a 4 estacas), com a área restante do pilar | §4.1 |
| Tirantes | Ver opções abaixo. Empuxo horizontal de cada estaca do contorno `H = R·lproj/z`, na direção da biela | §4.1 |
| Nó da estaca interna | Verificado contra fcd3 com 1,4 × R do M1, mais aviso de que a reação real dessa estaca depende da rigidez das estacas e deve ser conferida na capacidade geotécnica | Bavaresco §5 |
| Demais verificações | Iguais às da §4.1 por estaca; `y` pela D6 com a face espraiada (D13) | §4.1, §4.4 |
| Validação | B7 recalculado (abaixo); equilíbrio e simetria em pentágono, hexágono e hexágono com estaca central | B7 |

**Opções para os tirantes.** O Rodrigo escolheu a opção B em 16/10/2026.

| Opção | Regra | B7: lados / diagonais | Aço total no fundo |
|---|---|---|---|
| A | Anel: tirantes entre estacas vizinhas do contorno, força pelo equilíbrio de cada nó (regra atual de 3 e 4 estacas) | 1752,7 kN (40,3 cm²) / — | igual à regra dos 4/5 |
| B (escolhida) | Metade do empuxo no anel e metade em tirantes radiais, da estaca até o centro do pilar (nos polígonos pares viram diagonais contínuas de uma estaca à oposta) | 876,4 kN (20,2 cm²) / 1239,3 kN (28,5 cm²) | igual à A, distribuído como a fonte recomenda |
| C | Anel com 100 % e tirantes radiais com 50 % | 1752,7 kN / 1239,3 kN | 50 % a mais que A |

O tirante radial da opção B (e da C) vai da estaca do contorno até a estaca interna, quando há
uma só, ou até a estaca oposta, quando a linha entre as duas passa sob o pilar e cada uma é a
oposta da outra (diagonais dos polígonos pares). Sem parceiro (polígono ímpar sem estaca
central), o anel fica com todo o empuxo daquela estaca, como na opção A. A força no radial é
metade da projeção do empuxo na sua direção, e o anel equilibra o restante em cada nó.

**B7 recalculado** (γn = 1,2, sem o peso próprio D7 para comparar com a fonte, φ16, d′ = 58 mm):
Rd = 2400 kN por estaca, d = 2100 − 100 − 58 = 1942 mm, `y` = 186,8 mm, z = 1848,6 mm,
lproj = 1909 mm nas estacas de canto (igual à fonte: √2·(160 − 100/4) cm), H = 2478,7 kN.

| Grandeza | Fonte (Pd com peso próprio, γn = 1, z = 200 cm) | Recalculado | Diferença |
|---|---|---|---|
| lproj e θ da estaca de canto | 190,9 cm; 46,33° (tg 1,048) | 190,9 cm; tg 0,968 | braço `z = d − y/2` e d′ (D8) |
| Tirante dos lados (50 %) | 758,35 kN (17,44 cm²) | 876,4 kN (20,16 cm²) | +15,6 %: γn e braço menor |
| Tirante das diagonais (50 %) | 1072,47 kN (24,66 cm²) | 1239,3 kN (28,51 cm²) | +15,6 %, mesma razão |
| Nó da estaca central | 8,74 MPa ≤ 9,64 MPa (com 1,4) | a calcular na implementação | — |

A diferença é a mesma nos dois tirantes, (2400/2247)·(2000/1848,6) = 1,156, o que confirma que
a geometria das bielas é a da fonte. MEF da D14 no B7 (malha 210 mm): tração de 1837 kN no
plano x = −800 mm, contra 3505 kN dos tirantes do M5 que o cruzam em qualquer das opções.

## 4.7 Estacas como apoios elásticos no MEF (especificação, D16 aprovada)

Objetivo: tornar a conferência por MEF (D14) útil nos blocos com estaca interna. Com apoios
rígidos, a estaca sob o pilar atrai muito mais carga do que o M1 dá e a comparação é invalidada
pela regra de 1 % das reações. Na prática a estaca recalca e encurta, e a carga se redistribui.

**Protótipo no B7** (quincôncio de Bavaresco, Nd = 10 000 kN sem γn nem peso próprio, C30,
malha de 210 mm, cerca de 30 s por análise), com a cabeça de cada estaca rígida e uma mola
axial `k` igual em todas:

| k [kN/mm] | Estacas de canto (M1: 2000 kN) | Estaca central (M1: 2000 kN) |
|---|---|---|
| rígido (D14) | 1418 kN (−29 %) | 4332 kN (+117 %) |
| 2000 | 1946 kN (−2,7 %) | 2216 kN (+10,8 %) |
| 720 (E·A/L com E = 30 GPa, estaca 60×60 de 15 m, só o fuste) | 1979 kN (−1,0 %) | 2083 kN (+4,1 %) |
| 200 | 1994 kN (−0,3 %) | 2024 kN (+1,2 %) |
| 50 | 1999 kN (−0,1 %) | 2006 kN (+0,3 %) |

A soma das reações bate com a carga em todos os casos (erro < 10⁻⁶). O resultado depende
muito de `k`, e `k` depende do solo, da estaca e do comprimento: não há valor normativo para
ele (a NBR 6122:2019 não fixa rigidez de estaca), então o programa não inventa um padrão.

**Especificação (D16).**

| Etapa | Regra | Fonte |
|---|---|---|
| Entrada | Rigidez axial opcional de cada estaca, `k` [N/mm na entrada interna, kN/mm na tela], vinda do projeto geotécnico (prova de carga, análise de recalque). Vazia = apoio rígido, exatamente como na D14 | ADR-007 |
| Modelo | Cabeça de cada estaca rígida (todos os nós da área da cabeça com o mesmo deslocamento vertical, por equação), ligada a uma mola axial `k`; a restrição horizontal isostática da D14 não muda | D14 |
| Mistura | Estacas com e sem `k` no mesmo bloco: as sem `k` ficam rígidas, com aviso de que a mistura concentra carga nas rígidas | — |
| Reações | Com molas, a reação do MEF deixa de ser critério de validade: vira verificação de comparação com o M1, com alerta quando alguma estaca passa a reação do M1 em mais de 10 % ("M1 subestima a reação da estaca"). Sem molas, continua o critério de 1 % da D14 | D14, D15 |
| Tirantes e nós | Mesmas comparações da D14, agora também nos blocos com estaca interna | D14 |
| M1 | Continua com estacas de mesma rigidez. Com `k` diferentes entre estacas, aviso de que o M1 não considera a diferença | M1 |
| Ajuda na tela | Texto de apoio, sem valor padrão: para estaca de ponta, `k ≈ Ecs·A/L` só do fuste é um limite superior; estacas de atrito são mais flexíveis | — |
| Auditoria | Os valores de `k` usados entram nos parâmetros da trilha do MEF | CLAUDE.md §8 |

## 4.8 M5 para estacas em fileiras desencontradas (especificação, D17 aprovada)

Objetivo: levar o M5 aos estaqueamentos em fileiras paralelas deslocadas entre si (5-4, 3-2-3,
4-3-4, 4-2-4 e os demais padrões de 7 a 30 estacas do CRSI), que hoje são recusados porque não
formam grade (D13) nem polígono com as estacas internas sob o pilar (D15). Fontes: curso "Blocos
de Coroamento Complexos" (TQS), lâminas "Expandindo a ideia para blocos com várias estacas",
exemplo de 9 estacas em disposição 5-4 sob pilar-parede; CRSI Design Guide for Pile Caps,
Fig. 4.4 (padrões de 2 a 30 estacas); Gomes (2015) para o critério de escolha dos tirantes, já
adotado na D12.

**O que a fonte mostra.**
- As bielas saem do centro de isoáreas do pilar (partes de mesma área, uma por estaca) e chegam
  ao centro da estaca, com as verificações de Fusco nos nós (a NBR 6118 e as regras do M5 já
  cobrem isso).
- Os tirantes formam uma rede triangulada: um tirante por fileira, entre estacas vizinhas, e
  diagonais em zigue-zague entre fileiras vizinhas.
- A força em cada tirante é a projeção da biela de cada estaca, `Tx = Td·cos α` e `Ty = Td·cos β`,
  estaca a estaca, sem acumular ao longo da fileira. É o mesmo procedimento da planilha de N
  estacas, que já vimos na D13 que não equilibra os nós (§4.4). As lâminas não trazem números.

**Achados.**
- A rede de fileiras e diagonais é isostática só com duas fileiras ou quando as fileiras internas
  têm 2 estacas (5-4, 3-2-3). Cada estaca a mais numa fileira interna acrescenta uma barra
  redundante (4-3-4 tem 1, 5-4-5 tem 2), e o equilíbrio dos nós sozinho não decide as forças.
  O critério da D12 (mínimo de `Σ F·l`, Gomes eq. 3.7) decide, e já está no programa.
- Isoáreas de mesma área só equilibram as componentes horizontais das bielas (`Σ H = 0`) quando as
  reações são iguais. Com isoáreas proporcionais às reações, deslocadas da excentricidade da carga
  `e = M/N`, o equilíbrio é exato para qualquer carga: `Σ R·o = Σ R·p` é a própria condição do M1.
- Sob momento, ainda sobra um momento em planta pequeno (nos protótipos, até 0,5 % do maior
  empuxo), porque as isoáreas não são a distribuição exata das tensões do pilar.
- Em layouts simétricos o mínimo de `Σ F·l` costuma ter vários ótimos, e o programa linear devolve
  um deles, assimétrico. Entre os ótimos, o de menor `Σ F²` é único e mantém a simetria.

**Especificação (D17).**

| Etapa | Regra | Fonte |
|---|---|---|
| Escopo | Um pilar (vários pilares pelo pilar fictício, D10); estacas em 2 ou mais fileiras retas paralelas a x ou a y (o eixo com menos níveis de coordenada), todas com 2 ou mais estacas. Só entra o que a D13 e a D15 recusam: grades e polígonos com estaca central sob o pilar (2-1-2, 2-3-2) não mudam. Layout sem fileiras continua bloqueado com aviso | CRSI Fig. 4.4; TQS |
| Origem das bielas | Isoáreas: o pilar é dividido em uma faixa por fileira, com largura proporcional à soma das reações da fileira, e cada faixa em uma parte por estaca, na ordem da fileira, com largura proporcional à reação; a biela sai do centroide da parte. Com reações iguais, é a divisão em partes de mesma área da fonte e, numa grade, a da D13 | TQS; D13 |
| Excentricidade | As origens são deslocadas de `e = Σ R·p / Σ R − centro do pilar` (o `e = M/N` do M1), para fechar `Σ H = 0`. Se a origem deslocada sair da seção do pilar, o bloco é recusado com aviso | M1 |
| Profundidade `y` | D6 com a face espraiada (D13), como hoje | §4.1, §4.4 |
| Tirantes | Candidatos: os lados da triangulação de Delaunay das estacas (fileiras, diagonais entre fileiras e os lados do contorno). Força pelo mínimo de `Σ F·l` com tração apenas, sujeito ao equilíbrio de cada estaca com o empuxo `H = R·lproj/z`; desempate da D12 (tirante fora de x e y pesa 0,1 % a mais) e, entre os ótimos, o de menor `Σ F²`. Sem solução só com tração, o bloco é recusado | Gomes eq. 3.7; D12 |
| Resíduo | Antes do programa linear, os empuxos recebem a menor correção que zera a resultante e o momento em planta. A correção relativa ao maior empuxo vai para a trilha de auditoria; acima de 1 %, aviso | — |
| Detalhamento | Igual ao da D13: trechos alinhados formam barra contínua, ancoragem verificada nas pontas de cada barra (as diagonais são barras isoladas, ancoradas nas duas estacas), malha de 20 % com a soma das projeções | NBR 6118:2023, 22.7.4.1.1 e 22.7.4.1.2 |
| Demais verificações | Iguais às da §4.1 por estaca (fcd1, fcd3, `0,57 ≤ tg θ ≤ 2`, `y/d ≤ 0,3`) | NBR 6118:2023, 22.3.1 e 22.3.2 |
| Validação | Equilíbrio exato e simetria em 5-4, 3-2-3, 4-3-4 e 4-2-4, com e sem momento; MEF da D14 com molas da D16 no 3-2-3 (abaixo); a lógica da D13 e da D15 continua passando nos testes atuais | D14, D16 |

**Protótipo.** Estacas φ60 com espaçamento de 150 cm e fileiras a 129,9 cm (triângulo
equilátero), borda de 75 cm, C30, γn = 1,2 e D7.

| Bloco | Tirantes do M5 (D17) | MEF da D14 |
|---|---|---|
| 3-2-3, 450×410×150 cm, pilar 80×80, Nd = 6000 kN | fileiras 894,1 kN; lados em y 742,3 kN; diagonais centrais 449,2 kN e externas 41,3 kN | com molas k = 720 kN/mm (reações a menos de 4 % do M1): planos x = ±37,5 cm 2113 kN contra 2237 kN do M5 (−6 %); x = ±112,5 cm 633 kN contra 1830 kN; y = ±65 cm 1604 kN contra 2334 kN (−31 %). Com apoios rígidos, a fileira do meio atrai carga e a comparação é invalidada pelo critério de 1 % |
| 5-4, 750×280×200 cm, pilar 200×40, Nd = 9000 kN | fileira de 5: 1247,2 e 1870,8 kN; fileira de 4: 1399,7 e 1866,3 kN; diagonais de 105,1 a 420,3 kN; a rede escolhida é a da figura da fonte | — |

O MEF fica abaixo do M5 em todos os planos, mais perto na direção das fileiras. A regra das
isoáreas pesa pouco: no 5-4, dividir o pilar-parede em 9 partes iguais ao longo do comprimento,
como na figura da fonte, muda `Σ F·l` em 1 % e o maior tirante em 7 %.

## 4.9 Escolha de barras (especificação, D18 proposta)

Objetivo: transformar as áreas de aço do resultado em barras (quantidade, diâmetro e
espaçamento), conferir se cabem nas faixas sobre as estacas e usar a área efetiva na ancoragem.
Hoje o programa entrega só `As` e o diâmetro digitado, e a ancoragem supõe `As,calc/As,ef = 1`.

**Achados no protótipo** (agregado de 19 mm, brita 1).
- B1 com φ16: tirantes de 3 φ16 (6,03 cm²) e 2 φ16 (4,02 cm²), com folga nas faixas de 480 mm.
- B2 com φ25, o diâmetro da planilha de origem: o tirante central em x pede 17 φ25, que ocupam
  825 mm numa faixa de 1,2 × 600 = 720 mm. Não cabe numa camada. Com φ32 cabe: 11 φ32
  (88,47 cm²) em 672 mm; o `d′` da D8 muda e a área sobe 0,4 % (80,43 cm²).
- B7 com φ16: lados 11 φ16 e diagonais 15 φ16 (559 de 720 mm); cabe.
- Malha de distribuição com o menor diâmetro dá espaçamentos de 5 a 8 cm no B2 e no B7, que não
  são executáveis na prática; por isso o espaçamento mínimo de 10 cm abaixo.

**Especificação (D18).**

| Etapa | Regra | Fonte |
|---|---|---|
| Série de diâmetros | 6,3; 8; 10; 12,5; 16; 20; 25; 32; 40 mm (CA-50) | NBR 7480 (não está em NORMAS; série comercial usual, a confirmar) |
| Agregado | Nova entrada `max_aggregate_size`, padrão 19 mm (brita 1), editável | 18.3.2.2 |
| Tirantes: quantidade | `n = ⌈As / Aφ⌉` com o φ escolhido pelo usuário; numa barra contínua (trechos alinhados, D13), `n` do trecho mais carregado vale para a barra toda | 22.3.3 |
| Tirantes: cabe na faixa | Uma camada: `n·φ + (n − 1)·ah ≤ 1,2·φestaca`, com `ah` da 18.3.2.2. Se não couber, ver a decisão abaixo | 22.7.2.1 a), 18.3.2.2 |
| Ancoragem | `ℓb,nec` com `As,calc/As,ef = As / (n·Aφ)`, o que reduz o comprimento exigido | 9.4.2.5 |
| Malha de distribuição | Menor φ da série com espaçamento entre 100 mm (mínimo prático, padrão nosso) e o máximo da 20.1, `mín(2h; 200 mm)`; espaçamento arredondado para baixo de 10 em 10 mm | 22.7.4.1.2, 20.1 |
| Bloco flexível | Barras de flexão com o φ do usuário e a mesma regra de espaçamento; se o espaçamento ficar abaixo de 100 mm, sobe o φ | 20.1 (D9) |
| Suspensão e armadura lateral | Sem mudança (só área ou alerta, D11) | 22.7.4.1.3, 22.7.4.1.5 |
| Saída | Cada armadura ganha quantidade, espaçamento e área efetiva; o memorial e a tela mostram "11 φ32 (88,47 cm²)" e "φ16 c/15" | ADR-009 |

**Decisão pendente: tirante que não cabe na faixa.**
- (A) Avisar e deixar o usuário subir o diâmetro. O resultado sai com o aviso.
- (B) O programa sobe o φ pela série até caber e refaz o modelo, para o `d′` da D8 acompanhar a
  barra real (recomendada). No B2, φ25 vira φ32. Se nem φ40 couber, aviso como em (A).
- (C) Aceitar segunda camada, com `d′` no centroide do grupo de barras e `av` da 18.3.2.2.

## 5. Benchmarks propostos

Valores de referência serão **recalculados por nós** e conferidos contra a publicação. Diferenças
são registradas, nunca copiadas às cegas (ver B1).

| ID | Caso | Fonte | O que valida | Tolerância |
|---|---|---|---|---|
| B1 | Bloco 4 estacas, pilar 20×65, Fk = 700 kN, φ40, L = 120 cm, h = 100 cm, C35 | Macedo 2022, §6.1 (Tab. 6.1) | M3, M4, M5, M6 no mesmo caso | As < 2 % |
| B2 | Bloco 8 estacas (4×2), pilar 209×30, C35, φ60, h = 140 cm | Planilha "Bloco sobre N estacas" | M5 para N estacas (§4.4), malha 20 %, armadura mínima | As < 2 % contra o recalculado; geometria das bielas contra a fonte |
| B3 | 17 ensaios de Blévot & Frémy (4N2, 4N4, séries de 4 estacas) | Santos et al. 2019, Tab. 1 | Carga de ruptura prevista × ensaio, por método | Relatório de razão Fprev/Fensaio (não é teste de igualdade) |
| B4 | Exemplos de 5, 6, 7 e 16 estacas (simétricos e assimétricos) | CRSI Design Guide, cap. 8 | M1 (reações com momentos e estaqueamento assimétrico) | Reações < 1 % |
| B5 | Exemplo de validação do programa 3D | Gomes 2015, §5.1 | M7 e futura verificação MEF | Forças nas barras < 1 % (recalculadas) |
| B6 | Bloco com 3 pilares; pela figura, 330×300×140 cm e 12 estacas φ30 em grade 4×3 (o texto diz 200×200 cm e 16 estacas) | Macedo 2022, §6.2, Fig. 5.1/6.6 | M8 (D10) confrontado com M7 (D12) | Pilar fictício com mais tração que o M7 em x e em y; As da fonte não comparável (dados inconsistentes) |
| B7 | Bloco 5 estacas em quincôncio (B05P01), 420×420×210 cm, estacas 60×60 a 160 cm do centro, pilar 100×100, Nd = 10 000 kN, C25 | Bavaresco 2016, §3.1 e §5 | M5 fora de grade (§4.6), regra dos 4/5 | Geometria das bielas contra a fonte; tirantes contra o recalculado |

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
| D6 | Profundidade `y` do nó CCC (Santos/Stucchi): equilíbrio horizontal do nó, com a compressão horizontal que equilibra os tirantes atuando sob fcd1 numa faixa de altura `y` (ver §4.1); face espraiada a 45° pela D13 (§4.4) | Aprovada (Rodrigo, 13/10/2026) |
| D7 | Peso próprio do bloco = 5 % da força normal de cálculo de cada caso, no centro do bloco (NBR 6122:2019, 5.6 pede no mínimo 5 % da carga permanente; a normal de cálculo inclui variáveis, então fica a favor da segurança). Evita usar peso específico e γg, ainda não pinados | Aprovada (Rodrigo, 13/10/2026) |
| D8 | `d′` (cabeça da estaca ao eixo do tirante) = cobrimento + φ/2 do tirante | Aprovada (Rodrigo, 13/10/2026) |
| D9 | Bloco flexível: flexão nas seções S1 do CEB-70 com As pela NBR 6118 (17.2.2), cisalhamento 19.4.1 a d da face e punção no pilar 19.5 (C e C′), conforme §4.2; punção nas estacas de canto só alerta | Aprovada (Rodrigo, 13/10/2026) |
| D10 | Vários pilares: pilar fictício de área equivalente (área = soma das áreas, lados na razão √(Sx/Sy) do grupo, na resultante das normais de cada caso), com verificação do nó de cada pilar real; o resultado deve ser confrontado com o modelo de treliça 3D (M7) quando ele for implementado | Aprovada (Rodrigo, 13/10/2026) |
| D11 | Armadura de suspensão (22.7.4.1.3): sem método de cálculo na norma nem nas referências; o programa mantém o alerta e o item de área zero no resultado | Aprovada (Rodrigo, 13/10/2026) |
| D12 | Treliça 3D (M7) para confrontar D10: ótimo de `Σ Ft·lt` (Gomes eq. 3.7) por programa linear sobre todas as ligações, com planos e reações iguais aos do M5, verificações de cruzamento e inclinação depois do ótimo, e alerta quando o pilar fictício dá menos tração que o M7; adiciona numpy e scipy (§4.3) | Aprovada (Rodrigo, 13/10/2026) |
| D13 | M5 para N estacas em grade retangular: pilar dividido em nx × ny partes, tirantes por linha e coluna com força por equilíbrio dos nós, face do nó D6 espraiada a 45° em todos os blocos (§4.4) | Aprovada (Rodrigo, 13/10/2026) |
| D14 | Verificação por MEF linear (gmsh + CalculiX) dos blocos rígidos: apoios rígidos nas áreas das estacas, cargas como pressão nos pilares, tração nos planos entre linhas de estacas contra o M5 (alerta acima de 10 %) e tensão média nos nós contra fcd1/fcd3; só comparação, sob demanda (§4.5) | Aprovada (Rodrigo, 16/10/2026) |
| D15 | M5 para estacas fora de grade: contorno convexo com bielas da regra atual, estacas internas sob o pilar com biela vertical (4/5 generalizada) e nó verificado com 1,4 × R, tirantes metade no anel e metade radiais (opção B da §4.6) | Aprovada (Rodrigo, 16/10/2026) |
| D16 | Estacas como apoios elásticos no MEF: rigidez axial opcional por estaca dada pelo usuário (sem valor padrão), cabeça rígida com mola; com molas, reações do MEF comparadas ao M1 com alerta acima de 10 % em vez do critério de validade de 1 % (§4.7, ADR-007) | Aprovada (Rodrigo, 16/10/2026) |
| D17 | Fileiras desencontradas: isoáreas do pilar proporcionais às reações e deslocadas da excentricidade, tirantes na triangulação das estacas pelo mínimo de `Σ F·l` (critério da D12) e, entre os ótimos, o de menor `Σ F²` (§4.8) | Aprovada (Rodrigo, 17/10/2026) |
| D18 | Escolha de barras: quantidade pelo φ do usuário, uma camada na faixa 1,2·φ com espaçamento da 18.3.2.2, ancoragem com a área efetiva, malha com φ mínimo e espaçamento entre 100 mm e o máximo da 20.1 (§4.9) | Proposta (Claude, 17/10/2026) |

## 7. Ainda falta neste documento

- Completar as linhas **Pendente** (fbd, fctm, cobrimento, combinações).
- Fórmulas completas de M3–M5 para 2, 3 e 4 estacas, com unidades N, mm, MPa.
- Punção nas estacas de canto e de borda (perímetro reduzido) para blocos flexíveis.
