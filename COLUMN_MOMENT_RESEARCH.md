# Column Design Moments to BS 8110 — Research & Verification

*Prepared for the `mdm` (Hardy Cross) tool. Sources: BS 8110-1:1997 (in `src/assets/`),
Oyenuga *Reinforced Concrete Design* (`oyenuga.pdf` — the book your screenshots are from),
Fapohunda *Limit State Design* (`...fapohunda...pdf`), plus CSI/ETABS documentation and
industry references (links at the end).*

---

## 0. TL;DR — your three questions answered

1. **"Is moment distribution standard, or a workaround?"**
   It is **the standard hand method sanctioned by the code itself.** BS 8110-1:1997
   **clause 3.2.1.2.5** says, verbatim, that column ultimate moments "may be calculated by
   **simple moment distribution procedures**, on the assumption that the column and beam ends
   remote from the junction under consideration are fixed and that the beams possess **half
   their actual stiffness**." You are not switching to a hack — you are switching to the method
   the code names. Do it.

2. **"Do ETABS etc. do this?"**
   No — but that doesn't make the subframe method non-standard. ETABS/SAP/Robot run a **full
   3D direct-stiffness (matrix/FE) analysis** of the *entire* frame to get raw moments, then
   apply BS 8110 only at the *design* stage (minimum eccentricity, slender additional moment,
   biaxial). The **simplified sub-frame + moment distribution** is the code's explicitly-permitted
   *hand* alternative (cl 3.2.1.2.1–3.2.1.2.5) for exactly the situation where you don't want to
   assemble the whole 3D stiffness matrix. Both are "standard"; they sit at different points on
   the effort/accuracy curve. For a teaching/checking tool, the subframe method is the right target.

3. **"What flow should I implement?"**
   The canonical flow in §2 below. The good news: **you already have the hard part** — your
   `solver.py` `moment_distribution()` is a working distribution/carry-over engine. Column
   moments need only a *one-joint* distribution (no carry-over iteration at all), so it's a
   simpler special case of what you've already built.

---

## 1. The three code-sanctioned routes (pick your altitude)

BS 8110 cl 3.2.1 offers a ladder from rigorous to simple. All are legal:

| Route | What it is | BS 8110 clause | Used by |
|---|---|---|---|
| **A. Full frame** | Assemble & solve the whole 2D/3D frame elastically (Hardy Cross or matrix) | 3.2.1.2.1 | ETABS, SAP (3D FE) |
| **B. Sub-frame** | One floor of beams + columns above & below, remote ends fixed | 3.2.1.2.1 / 3.2.1.2.3 | RCC spreadsheets, exams |
| **C. Column-only sub-frame** | The column + only the beams framing directly into it; distribute the beam FEM to the column by stiffness | **3.2.1.2.5** | **Oyenuga (your book)** |

Route **C** is what every one of your screenshots does, and it's what I recommend the tool
implement. It is a **single-joint moment distribution**: there is only one free joint (the
beam–column node), so the unbalanced moment is distributed **once** with **no carry-over**.

> **Key convention (all sources agree):** when the far ends of the adjacent beams are taken as
> fixed, use **half the beam stiffness** (½·4EI/L = 2EI/L). This is in cl 3.2.1.2.5, in
> Fapohunda §4.3.3.1, and in the Structville/FPP references. *Oyenuga's worked examples do **not**
> halve the beam stiffness* — this is the one point where your textbook is less conservative than
> the code. See §5.

---

## 2. The canonical flow (the "proper flow" you were missing)

This is the end-to-end pipeline. Steps 1–2 you partly have; steps 3–6 are the gap; steps 7–10
map onto your existing `column.py`.

### Step 1 — Axial load take-down (the "loading on columns")
Per **cl 3.8.2.3**, axial force may be found assuming **beams and slabs are simply supported**
onto the column. Accumulate top-down, floor by floor: roof load + slab tributary + beam/wall +
column self-weight, summing "from above" at each level. *(This is your screenshots
"7.5.4 Loading on Columns" and the house-example take-down — those reproduce correctly.)*

### Step 2 — Slab → beam load idealisation (two-way slabs, moments only)
For **moment** calculation the two-way slab reaction on a supporting beam is idealised as an
**equivalent UDL** (not the true triangular/trapezoidal shape):

```
short-span beam:  w_eq = (1/3)·w·lx
long-span  beam:  w_eq = (1/2)·w·lx·(1 − 1/(3k²)),   where k = ly/lx  (≥1)
```

`w` = ultimate slab pressure (kN/m²), `lx` = shorter slab span. Add the beam self-weight + wall
load to get the total UDL on the beam. **Verified exactly** against the office block:
`k=1.2 → 1/(3k²)=0.2315`, short = 20.83 (book 20.81), long = 24.02 (book 24.03). ✓

> Edge case: this idealisation assumes **equal restraint on all slab edges**. For a slab
> continuous one side / discontinuous the other, the true reactions differ; the code UDL is a
> "for moments only" simplification and is fine for column-moment estimation.

### Step 3 — Fixed-end moments on the beams
`FEM = w·L²/12` for a UDL (your `Span.fixed_end_moments()` already does the general case).
At an **internal** support the two adjacent beams both contribute; at an **external** (end)
support only one beam frames in, so there's a net unbalanced FEM → column moment.

### Step 4 — Member stiffnesses
```
Column:            K_col  = I_col / L_col            (EI/L; E cancels in the ratio)
Rectangular beam:  K_beam = I_beam / L_beam ,  I = b·h³/12
Flanged (T/L) beam:I = K·b_w·h³  with K from Oyenuga Fig 7.5 (a chart of hf/h vs bw/B)
```
For code-compliant work, **halve K_beam** (§1). Oyenuga uses full K_beam and full-fixity of
the *column* far end — internally consistent within the book, but not the code convention.
**Verified:** I_col = 213.6×10⁶, K_col(3.0m)=71.19, K_col(3.15m)=67.80, roof-beam K5=341.7,
K6=284.8, and all four flanged-beam K's match the book to 2 dp. ✓

### Step 5 — Distribute the unbalanced FEM to the column(s)
This is the single-joint distribution factor — the formula from your screenshot p.161:
```
M_col = M_FEM,beam · K_col / ( ΣK_col + ΣK_beam )
```
where the sum is over **every member meeting at that joint** (both columns if the joint has a
column above *and* below, and all beams). **Verified** across A1, A2, B2 at every level, e.g.
A1 roof: `18.13·71.19/(71.19+341.7+284.8)=1.85` ✓; A1 2nd-flr foot:
`79.81·71.19/(71.19+67.80+1322+1158)=2.17` ✓.

### Step 6 — Split between upper and lower column
The joint moment is shared between the column length above and below in proportion to their
stiffness:
```
M_col,upper = M_joint · K_upper/(K_upper+K_lower)   (and likewise lower)
```
Your screenshot does this as "moment on foot of col = …, moment on top of col = foot·K_top/K_bot".
**Verified:** A1 top = `2.17·67.80/71.19 = 2.066` ✓.

### Step 7 — Combine end moments into the column design moment
Per **cl 3.8.3.2** (braced, single axis), with `M1` = smaller end moment, `M2` = larger:
```
Mi = 0.4·M1 + 0.6·M2   ≥ 0.4·M2            (initial mid-height moment)
```
and the **design moment is the greatest of**:
**(a)** M2  **(b)** Mi + Madd  **(c)** M1 + Madd/2  **(d)** e_min·N.
For a **short** column Madd = 0, so it collapses to `max(M2, e_min·N)`. Oyenuga's
`M = 0.4M1 + 0.6M2` line is case (b)/(a) with Madd=0. **Verified:** A1 `0.4·1.85+0.6·2.17=2.04` ✓.

> ⚠️ Sign convention matters: for a column in **double curvature** take M1 **negative**. Your
> current `column.py` uses `max(abs(Mx_top), abs(Mx_bot), Mmin)` which silently assumes single
> curvature (both +). See §6.

### Step 8 — Minimum eccentricity (cl 3.8.2.4)
`e_min = min(0.05·h, 20 mm)` **per axis** — note it's a **cap at 20 mm**, i.e. `min`, not `max`.
`M_min = N·e_min`. Biaxially you need only exceed e_min about **one axis at a time**.

### Step 9 — Slenderness / additional moment (cl 3.8.3)
Short if `le/h < 15` and `le/b < 15` (braced) or `<10` (unbraced). If slender:
```
au = βa·K·h,  βa = (1/2000)(le/b')²  [Table 3.21],  K = (Nuz−N)/(Nuz−Nbal) ≤ 1
Madd = N·au                        Nuz = 0.45 fcu Ac + 0.95 fy Asc
```
`b'` = smaller dimension for uniaxial; for **biaxial**, `b'` = depth in the plane of bending
(cl 3.8.3.6). Add Madd into the case (b)/(c) checks of Step 7.

### Step 10 — Biaxial resolution (cl 3.8.4.5) → section design
When moments act about both axes, convert to an increased uniaxial moment:
```
if Mx/h' ≥ My/b':   Mx' = Mx + β·(h'/b')·My
else:               My' = My + β·(b'/h')·Mx
β = 1 − 7N/(6·b·h·fcu)  approx of Table 3.22 (β: 1.0→0.30 as N/bhfcu: 0→0.6)
```
Then design the section for (N, M') — your `calculate_strain_compatibility()` handles this last part.

---

## 2A. End conditions → effective height (Table 3.19 / 3.20)

The front half of Step 9, spelled out — this drives *whether the column is even slender* and
the whole additional-moment calc, so it must be right. Effective height (cl 3.8.1.6.1):

```
le = β · lo          lo = CLEAR height between end restraints (not centre-to-centre)
```

β comes from the **end conditions** at each column end (cl 3.8.1.6.2), scale 1→4, fixity
decreasing:

1. Monolithic to beams **≥ the column depth** in the plane considered (or a moment-carrying foundation).
2. Monolithic to beams/slabs **shallower** than the column depth.
3. Members giving only **nominal** rotational restraint.
4. **Unrestrained** against lateral movement *and* rotation (free end of an unbraced cantilever).

**Table 3.19 — braced β** (rows = top condition, cols = bottom):

| top ＼ bot | 1 | 2 | 3 |
|---|---|---|---|
| **1** | 0.75 | 0.80 | 0.90 |
| **2** | 0.80 | 0.85 | 0.95 |
| **3** | 0.90 | 0.95 | 1.00 |

**Table 3.20 — unbraced β:**

| top ＼ bot | 1 | 2 | 3 |
|---|---|---|---|
| **1** | 1.2 | 1.3 | 1.6 |
| **2** | 1.3 | 1.5 | 1.8 |
| **3** | 1.6 | 1.8 | — |
| **4** | 2.2 | — | — |

Notes: the tables are symmetric in top/bottom (so (1,4)=(4,1)=2.2). Condition **4 pairs only with
condition 1** — every other "4" combination is a dash (not permitted). `le,x` and `le,y` may
**differ** (different end conditions and/or clear heights per plane) — do not assume one β for both.

> **⚠️ Code bug (`column.py:135-147`).** The current β lookup collapses rows with
> `cond_top == 3 or cond_bot == 3` and invents `2,4 = 2.8`. It is wrong for:
> braced **(2,3)/(3,2)** → gives 0.90, should be **0.95**; braced **(3,3)** → 0.90, should be
> **1.00**; unbraced **(1,3)/(3,1)** → 2.0, should be **1.6**; **(2,3)/(3,2)** → 2.0, should be
> **1.8**; **(4,1)** → 2.0, should be **2.2**; **(2,4)** → 2.8, which is not a code value at all.
> The braced (2,3)/(3,3) and unbraced (4,1) errors **underestimate le** → a slender column can be
> mis-read as short and skip the additional moment. Replace the if/elif chain with a direct
> 2-D table lookup keyed on (cond_top, cond_bot, braced).

---

## 3. Edge-case decision tree (which moments even exist)

The reason a corner column ≠ an internal column is **which beam FEMs cancel at the joint**. This
is the "edge cases" you were stuck on:

```
For each column, at each axis (x-x and y-y):
│
├─ Beams frame in on BOTH sides of the joint, roughly equal FEM?
│   └─ YES → the FEMs balance → net unbalanced ≈ 0 → NO significant column moment this axis
│            (design that axis for nominal/min-eccentricity only)
│
├─ Beam on ONE side only (external/edge joint)?
│   └─ YES → full beam FEM is unbalanced → distribute to column (Step 5). Moment EXISTS.
│
└─ Beams both sides but UNEQUAL (different span/load)?
    └─ Net = |FEM_left − FEM_right| distributed to column. Moment EXISTS (usually small).
```

Applying it to the classic 4 column types (your office block C1–C4 / A1,A2,B1,B2):

| Column | Position | x-x moment | y-y moment | Design as |
|---|---|---|---|---|
| **C1 / A1** | Corner | one beam only → exists | one beam only → exists | **Biaxial** |
| **C2 / A2** | Edge (top/bottom) | equal beams both sides → cancel → nominal | one beam only → exists | **Uniaxial** (y) |
| **C3 / B1** | Edge (left/right) | one beam only → exists | equal beams → cancel → nominal | **Uniaxial** (x) |
| **C4 / B2** | Internal | equal beams → cancel | equal beams → cancel | **Axial + nominal** (e_min only) |

This is exactly why Oyenuga writes "moments in x-x cancelled out, hence only y-y need be
considered" (A2) and "a truly central column in which all opposite beams balance out" (B2).

Other edge cases to handle in code:
- **Column above but not below** (top storey) or **below but not above** (at foundation): the
  joint stiffness sum ΣK_col has only one column term; the whole joint moment goes to the one
  column. At a pinned base, `k = 10` (nominal) per standard practice.
- **`M/N ≤ 0.6h` and low v** → no shear check needed (cl 3.8.4.6).
- **N > 0.2 fcu Ac** → no crack check needed (cl 3.8.6).
- **Ratio long/short side ≥ 3** → design as biaxial with zero minor-axis initial moment
  (cl 3.8.3.5), even if nominally uniaxial.
- **Unbraced slender** → Madd applied at the **stiffer** joint (cl 3.8.3.7), not mid-height.

---

## 4. Verification of your calculations — office block ✓, house example ✗

### Office block (Fig 7.4, fcu 25 / fy 410) — **reproduces to 3 s.f. everywhere.**
Loads, slab idealisation, all FEMs, all stiffnesses, and all column moments (A1, A2, B1, B2 at
roof / 2nd / 1st) match. Your understanding of the method is correct — trust this example as the
reference implementation.

### House example (Fig 10.5, fcu 20 / fy 250) — **contains the skipped steps & errors you sensed.**

| # | Location | Issue | Correct value |
|---|---|---|---|
| **1** | Col C1, Beam 1.A-D FEM | Text uses `w = 62 kN/m` but the stated FEM 118.294 back-solves to **w = 52.03**, not 62. `62·5.225²/12 = 141.05 ≠ 118.29`. A value was silently changed between lines. | If w=62, L=5.225 → **141.05**; if FEM=118.29 is right → w=52.03 |
| **2** | Col C1, Beam C.1-2 span | FEM 155.841 uses **L = 5.225 m**, but Fig 10.5 dimensions the grid 1–2 bay as **5.725 m** (5725). With 5.725 the FEM is **187.09**. Span taken inconsistent with the plan. | Confirm the true c/c span; if 5.725 → 187.09 |
| **3** | Col C1, final distribution | The printed result 3.691 needs a denominator of **3.251**, but the four listed stiffnesses sum to only **2.851** (0.077+1.441+0.437+0.896). ~0.4 of stiffness (a second column, or a mis-transcribed beam K) is **missing from the shown sum** though used in the arithmetic. | Denominator should be ~3.251; re-list the member K's |
| **4** | Col B3 (737 kN) | `0.05·N·h = 0.05·737·0.23 = 8.476 kNm`, but the line **prints 3.476**. The *correct* 8.476 is (correctly) used in the very next line `M/bh² = 8.476×10⁶/(230·230²) = 0.697`. So it's a **typo, not a calc error** — the design value is right. | 8.476 kNm (as used) |
| **5** | Col B3 FEM with continuity | `66·4.95²/12 − 35·2.03²/12 + 0.242·0.758²·112·4.95 = 199.8` ✓ (book 199.89). The extra `+0.242(0.758²)·112·4.95` term is a continuity/pattern-load correction — **not skipped, just unexplained.** | 199.8 ✓ |

**Net:** the *method* in the house example is sound and B3's final answer is fine; the defects are
in **Col C1** — an inconsistent beam load (62 vs 52), an inconsistent span (5.225 vs 5.725), and a
distribution denominator that doesn't match its own listed stiffnesses. Re-derive C1 from the
plan dimensions and the C1 result will move.

---

## 5. Where your textbook diverges from the code (decide deliberately)

1. **Beam stiffness halving.** Code (cl 3.2.1.2.5) says halve K_beam for far-fixed beams.
   Oyenuga uses **full** K_beam. Effect: the book gives the column a *smaller* share of the
   unbalanced moment (larger denominator) → **less conservative** column moments. If you want
   code-compliant output, halve the beam K in the distribution. (Your office-block numbers match
   the book precisely *because* the book didn't halve — so this is a deliberate fork, not an error.)

2. **Column far-end fixity vs continuity.** Both books fix the remote column end. Fine for a hand
   sub-frame.

3. **Load pattern (cl 3.2.1.2.2).** Neither hand example runs the alternate-span pattern loading
   (max on one span, min on the other) that the code asks for to maximise column moment. For a
   full tool you'd want to expose both the "all spans loaded" and "alternate spans" cases and
   take the envelope.

---

## 6. How this maps to your code (`src/mdm/design/column.py` + a new frame step)

**What you have:** `design_column_section()` takes `Mx_top, Mx_bot, My_top, My_bot` as **inputs**
— i.e. it assumes the moments are already known. `solver.py::moment_distribution()` is a full
multi-joint distributor with carry-over. So the **gap is only Steps 2–6**: turning slab+beam
loads into those four end moments.

**Recommended addition:** a `column_moments.py` that, given the tributary beams at a joint
(span, load, I, far-end condition) and the columns above/below, does the **single-joint
distribution** and returns `(Mx_top, Mx_bot, My_top, My_bot)` to feed the existing
`design_column_section()`. This is a ~1-joint special case of your solver — no iteration needed.

**Concrete issues I noticed in the current `column.py` while researching (worth fixing when you
implement the flow):**

- **L135–147 effective-length β table is wrong.** The `is_braced` if/elif chain doesn't match
  BS 8110 Table 3.19/3.20 (see §2A): it lumps all condition-3 cases together and fabricates
  `2,4 = 2.8`. Underestimates le for braced (2,3)/(3,3) and unbraced (4,1) → can mis-classify a
  slender column as short. Replace with a direct `β[braced][cond_top][cond_bot]` table lookup, and
  allow **separate β/le for the x and y planes** (cl 3.8.1.6.1 permits different end conditions per
  plane; the code currently forces `lex = ley`).
- **L166–167 minimum eccentricity is inverted.** Code: `emin_x = max(0.05*h, 20.0)`. BS 8110
  cl 3.8.2.4 is `e_min = min(0.05h, 20 mm)` (20 mm is a **cap**, not a floor). For h=230,
  `0.05·230=11.5` → should be **11.5 mm**, current code gives 20 mm; for h=600 → should be
  **20 mm** (cap), current code gives 30 mm. This over-estimates M_min for large sections and
  under-estimates for small ones. → use `min(...)`.
- **L178–179 single-curvature assumption.** `Mx = max(abs(top),abs(bot),Mmin)` ignores the
  `Mi = 0.4M1+0.6M2` combination and the double-curvature sign rule (Step 7). Implement the
  "greatest of (a)–(d)" check instead.
- **L184–190 additional-moment axis pairing.** `βa` for the minor axis uses `ley/h`; for uniaxial
  minor-axis bending `b'` should be the **smaller** dimension (cl 3.8.3.1 note), and for biaxial
  it should be the **plane-of-bending depth** (cl 3.8.3.6). Current pairing is mixed; align `b'`
  per Step 9.
- **L208 `Nuz` for K** uses a fixed 1 % steel guess; fine as a first pass, but the code comment
  ("Rough estimate") is right — iterate once Asc is known if you want cl 3.8.3.1's K.

None of these block the research conclusion; they're the punch-list for making the section-design
half match the moment half you're about to build.

---

## 7. Recommendation

- **Adopt the sub-frame single-joint moment-distribution method (Route C).** It is code-sanctioned
  (cl 3.2.1.2.5), it's what your reference book uses, and you already own the distribution engine.
- **Implement the Step 2–6 pre-processor** to generate the four end moments, then keep feeding
  `design_column_section()`.
- **Make the beam-stiffness-halving a toggle** ("BS 8110 compliant" vs "Oyenuga textbook") so your
  output can match the book *and* be defensible.
- **Encode the §3 decision tree** so corner/edge/internal columns automatically drop the
  cancelling-moment axes to nominal — that's the edge-case handling you were stuck on.
- Don't chase full 3D FE (the ETABS route) for this tool; it's a different, much larger project
  and unnecessary for BS 8110 hand-method design/checking.

---

## Sources

- BS 8110-1:1997 — cl 3.2.1.2 (sub-frames), **3.2.1.2.5** (column moments by distribution),
  3.8.1.3/1.6 (slenderness, effective height, Tables 3.19/3.20), 3.8.2.3/2.4 (axial & min ecc.),
  3.8.3 (additional moments, Tables 3.21), 3.8.4.5 (biaxial, Table 3.22). *(local copy in `src/assets/`)*
- Oyenuga, *Reinforced Concrete Design* — Ch.7 Column Design (office block) & Ch.10 (house). *(`src/assets/oyenuga.pdf`)*
- Fapohunda, *Limit State Design of RC Structural Elements* — §4.3.3.1 sub-frame methods. *(`src/assets/...fapohunda...pdf`)*
- CSI/ETABS: [Concrete Frame Design Procedure](https://docs.csiamerica.com/help-files/etabs/Getting_Started/Concrete_Frame_Design_Procedure.htm), [Interactive concrete frame design](https://wiki.csiamerica.com/display/etabs/Interactive+concrete+frame+design)
- [FPP Engineering — Analysis of Sub-frame for Column Moment](https://knowledge.fppengineering.com/analysis-of-subframe-for-column-moment-worked-example/), [Design of Column to BS 8110 – overview](https://knowledge.fppengineering.com/design-of-column-to-bs-8110-an-overview/)
- [Structville — Design of RC Columns](https://structville.com/2020/10/design-of-reinforced-concrete-columns.html)
