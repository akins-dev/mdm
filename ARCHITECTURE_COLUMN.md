# Column Analysis & Design — Architecture

*Target: `mdm`. Turns the half-built "type-in-the-moments" column tool into a
**describe-the-frame → we-compute-the-moments → design → 3D visual** teaching tool.
Builds on the method in [`COLUMN_MOMENT_RESEARCH.md`](COLUMN_MOMENT_RESEARCH.md).*

---

## 0. The decision that reframes the whole feature

**Today** the student types `N, Mx_top, Mx_bot, My_top, My_bot` into the storey table
(`index.html` `storeyTbody`) and the server designs from those. **But computing those moments
is exactly what students are stuck on** — so the tool currently skips the hard, teachable part.

**Decision (decisive):** flip the input. The student describes the **sub-frame around the
column** — the beams framing in (span, load, size), the slab panels, and the storey heights —
and the tool runs the **Route-C single-joint moment distribution** (BS 8110 cl 3.2.1.2.5) to
*produce* the four end moments, then designs. Manual moment entry is kept as an "Advanced /
override" path so nothing regresses and experts can still poke values in.

Everything below follows from that flip.

---

## 1. Data flow (one screen, three tabs)

```
                 ┌─────────────── FRONTEND (index.html) ───────────────┐
  Frame + Loads  │  Column mode                                        │
  input  ─────►  │  ├─ "Frame & Loads"  (NEW, primary/pedagogical)     │
                 │  └─ "Direct Moments" (existing table, override)     │
                 └───────────────┬─────────────────────────────────────┘
                                 │  POST /analyze_column  { stack, loads, params }
                                 ▼
        ┌──────────────────── SERVER (server.py) ─────────────────────┐
        │  column_moments.build_column_stack(payload)                 │
        │     Step 1  axial take-down            ─┐                    │
        │     Step 2  slab → beam UDL             │ per joint,          │
        │     Step 3  beam fixed-end moments      │ per axis (x,y)      │
        │     Step 4  member stiffnesses          │ → returns          │
        │     Step 5  single-joint distribution   │   (Mx_top,Mx_bot,  │
        │     Step 6  split upper/lower column   ─┘    My_top,My_bot)   │
        │                     │  moments + step trace                  │
        │                     ▼                                        │
        │  column.design_column_section(...)  Steps 7–10 (fixed bugs)  │
        └──────────┬────────────────────┬──────────────┬──────────────┘
                   │ moment_trace_html   │ design_html  │ viz JSON
                   ▼                     ▼              ▼
        ┌──────────────────── FRONTEND render ────────────────────────┐
        │  Tab 1: 3D Model        (Three.js, upgraded)                 │
        │  Tab 2: Moment Analysis (Steps 1–6 calc-sheet + joint SVG)   │
        │  Tab 3: Design Report   (Steps 7–10 calc-sheet, existing)    │
        └─────────────────────────────────────────────────────────────┘
```

---

## 2. Backend modules

| File | Status | Responsibility |
|---|---|---|
| `src/mdm/design/column_moments.py` | **NEW** | Steps 1–6: frame description → four end moments + a step-by-step trace. The whole "moment engine". |
| `src/mdm/design/column.py` | **FIX** | Steps 7–10: design from moments. Fix the β-table, min-ecc, curvature, biaxial-b′ bugs from the research §6. |
| `src/mdm/design/bs8110.py` | **EXTEND** | Add β Table 3.19/3.20 and biaxial β Table 3.22 as plain data (reuse existing `STANDARD_BAR_AREAS`, `select_bar_arrangement`). |
| `src/mdm/server.py` | **EXTEND** | New `POST /analyze_column`; keep `POST /design_column` as the override path. |

**Why a new module, not the solver:** `solver.py::moment_distribution()` is a multi-joint
distributor *with* 0.5 carry-over. Column Route-C is a **single free joint, no carry-over** — a
strict, simpler special case. Reusing the heavy engine would obscure the teaching. We *do* reuse
`Span.fixed_end_moments()` (models/beam.py) for the beam FEMs and `row()/money()/fmt()` for the
calc-sheet HTML.

---

## 3. Data model (dataclasses in `column_moments.py`)

```python
@dataclass
class Beam:
    direction: str        # '+x' | '-x' | '+y' | '-y'   (which side of the joint)
    span: float           # m, centre-to-centre
    w: float              # kN/m  total UDL on the beam (or computed from slab, see Step 2)
    b: float; h: float    # mm, section (for I = b·h³/12; flanged handled via I_override)
    I_override: float = None      # mm⁴ for T/L flanged beams (Oyenuga Fig 7.5 chart value)
    far_end_fixed: bool = True     # remote end assumed fixed (cl 3.2.1.2.5)
    # slab inputs (optional — if given, w is derived in Step 2)
    slab_w: float = None; lx: float = None; ly: float = None; slab_side: str = 'short'

@dataclass
class Lift:                 # one storey length of column
    name: str              # "Ground", "1st", …
    height: float          # m, clear height  lo
    I_col: float           # mm⁴  (b·h³/12 about the axis, per plane)
    cond_top: int; cond_bot: int   # end conditions 1–4 (per this lift)

@dataclass
class Joint:               # the beam-column node at the TOP of a lift
    lift_below: Lift
    lift_above: Lift | None       # None at roof
    beams: list[Beam]             # 0–4 beams framing in
    N: float                      # kN axial at this level (from Step-1 take-down)

@dataclass
class ColumnStack:         # what the student builds in the storey table
    b: float; h: float; fcu: float; fy: float; cover: float; target_dia: float
    braced: bool
    halve_beam_stiffness: bool = True   # BS 8110 compliant (True) vs Oyenuga textbook (False)
    joints: list[Joint]
```

The frontend `storeys[]` array (already in `index.html`) grows a `beams[]` field per storey and
posts the whole stack.

---

## 4. The per-joint algorithm (the heart)

For each `Joint`, independently for the **x-x** and **y-y** planes:

```
1.  FEM_i   = w_i · L_i² / 12         for each beam i in this plane   (Span.fixed_end_moments)
2.  M_unbal = Σ (signed) FEM_i        left-side +, right-side −  →  cancellation falls out here
3.  K_beam_i = (I_i / L_i) · (0.5 if halve_beam_stiffness else 1.0)   [far-end fixed]
    K_col_up = I_col_up / L_up ;  K_col_low = I_col_low / L_low
4.  ΣK      = K_col_up + K_col_low + Σ K_beam_i
5.  M_joint = M_unbal · (K_col_up + K_col_low) / ΣK      (moment taken by the two columns)
6.  Mx_top(of lift below) = M_joint · K_col_low/(K_col_up+K_col_low)   ← at joint = top of lower lift
    Mx_bot(of lift above) = M_joint · K_col_up /(K_col_up+K_col_low)
```

Repeat at the joint at the **bottom** of each lift → each lift ends up with `(M_top, M_bot)` per
axis = the four numbers `design_column_section()` needs. Every line emits a trace entry
`{ref, formula, substitution, result}` rendered via `row()`.

**Acceptance test (non-negotiable):** reproduce the office-block example from the research to
3 s.f. — A1 roof `1.85`, A1 2nd-flr foot `2.17`, A1 top `2.066`, etc. A `tests/` script asserts
these before any UI work is trusted.

---

## 5. Edge cases — handled by construction, not special-cased

Because Step 2 sums the *actual* beams present, the corner/edge/internal logic is automatic:

| Beams present in a plane | Σ signed FEM | Result |
|---|---|---|
| one side only (corner/edge) | full FEM | moment exists |
| both sides, equal | ≈ 0 | cancels → nominal (min-ecc) |
| both sides, unequal | difference | small moment |

`classify(joint)` → `'corner' | 'edge-x' | 'edge-y' | 'internal'` is derived purely from which
`direction`s are populated, and drives the 3D colour + the "why" badge. The other edge cases from
research §3 (top-storey = no column above → all joint moment to lower lift; pinned base `k=10`;
long/short ≥ 3 → biaxial with zero minor initial moment) are explicit branches in Step 6 and in
`column.py`.

---

## 6. Frontend

**Input** — `columnInputSection` gets a sub-toggle:
- **Frame & Loads (default):** global section + a **per-storey beam editor** — for each storey, a
  compact 4-slot widget (+x/−x/+y/−y) where the student sets span, section, and *either* a direct
  UDL *or* slab (w, lx, ly). A "Column position" preset (Corner / Edge / Internal) pre-populates
  which slots exist so beginners aren't faced with a blank grid. `N` can be auto-accumulated from
  a slab pressure (Step-1 take-down) or typed.
- **Direct Moments (override):** the current `storeyTable`, unchanged.

**Output** — the existing `tabs` nav gains a third tab: **3D Model | Moment Analysis | Design
Report**. Moment Analysis renders the Step 1–6 trace (calc-sheet CSS already exists) plus the
joint SVG (below). Design Report is today's `design_column_section` HTML.

---

## 7. The 3D visual — decisive spec

Built with the **already-loaded** Three.js r128 + OrbitControls; extends `build3DScene()`. No new
libraries. Text via canvas-texture sprites (r128 has no CSS2DRenderer loaded).

**What is drawn**
1. **Column stack** — the current stacked `BoxGeometry` lifts (kept). Selected lift highlighted.
2. **Framing beams at the selected joint** — horizontal boxes along ±X/±Z, only for the beams
   that exist (drives home corner vs internal visually). Length = ½ span (scaled), section = beam
   b×h.
3. **Tributary slab** — the faint slab panel (exists) upgraded to show the **two-way yield-line
   split** (triangles/trapezoids) so students see *where the beam UDL comes from* (Step 2).
4. **Force glyphs at the joint** — a downward arrow labelled `N`; curved arrows (Torus arcs)
   about X and Z labelled `Mx`, `My`, sense from sign.
5. **Deflected-shape toggle** — bow the selected lift in single/double curvature from the
   `M_top,M_bot` signs — the visual for curvature and the slender additional moment.

**Colour coding**
- Position badge: corner / edge / internal (informational).
- After design: tint the designed lift by utilisation `Asc_req/Asc_max` — green `<0.5`,
  amber `<0.8`, red `≥0.8` or INADEQUATE.

**Interaction** — click a lift (raycaster exists) → selects that storey, redraws its beams/forces,
and a small HUD lists `N, le/h, short|slender, Mx, My, position`.

**2D companion (Moment Analysis tab)** — an SVG "distribution wheel": the joint at centre, spokes
for `K_col_up, K_col_low, K_beam_i` with their distribution fractions and the resulting `M_joint`
split — same hand-drawn calc aesthetic as the beam BMD/SFD SVGs.

**Server → frontend viz contract**
```json
{ "column": {"b":300,"h":400},
  "lifts":  [{"id":1,"name":"Ground","height":3.0,"N":1500,
              "Mx_top":2.1,"Mx_bot":2.0,"My_top":1.1,"My_bot":1.0,
              "le_h":9.0,"slender":false,"util":0.63,"position":"corner"}],
  "joints": [{"liftId":1,"beams":[{"dir":"+x","span":6,"w":24,"b":600,"h":225,
              "fem":72,"contributes":true}],
              "Kcol_up":67.8,"Kcol_low":71.2,"Mx":2.1,"My":1.1}] }
```

---

## 8. Pedagogical layer (the stated aim)

- **Show the work:** every value is `formula → substitution → result` (the trace), not a bare
  number — the same calc-sheet rows students already see for beams.
- **Live "why this column" badge:** e.g. *"CORNER column — beams frame in on +x and +y only, so
  both axes carry moment → design biaxially."* Generated from `classify()`.
- **BS 8110 vs textbook toggle:** the `halve_beam_stiffness` switch, so students see the moment
  change and understand the code convention (research §5).
- **Cross-links** to the exact clause on every step (`row()`'s ref column), matching the beam side.

---

## 9. Reuse map

| Need | Reuse |
|---|---|
| Beam FEM & stiffness | `models/beam.py::Span.fixed_end_moments()`, `.stiffness()` |
| Calc-sheet rows / number fmt | `design/design.py::row`, `models/beam.py::money,fmt` |
| Bar selection & areas | `bs8110.py::select_bar_arrangement`, `get_bar_area`, `STANDARD_BAR_AREAS` |
| Section capacity | `column.py::calculate_strain_compatibility` (keep) |
| 3D scaffold | `index.html` `init3D/build3DScene/animate/onMouseClick` (extend) |
| Tabs / status / print | existing `tabs`, `colStatus`, `print-area` wiring |

---

## 10. Phased build plan (each phase independently shippable)

- **Phase 1 — Moment engine.** `column_moments.py` + `tests/test_column_moments.py` reproducing
  the office-block numbers. *No UI.* Fix `column.py` bugs (β table, min-ecc, curvature, biaxial b′)
  with a regression check. **Gate: office-block example matches to 3 s.f.**
- **Phase 2 — Wire it up.** `POST /analyze_column`; "Frame & Loads" input editor; route computed
  moments into `design_column_section`; Moment Analysis tab shows the trace. Direct-Moments path
  still works.
- **Phase 3 — 3D upgrade.** Beams at joint, tributary slab split, N/Mx/My glyphs, utilisation
  tint, HUD, deflected-shape toggle, distribution-wheel SVG.
- **Phase 4 — Pedagogy polish.** Position badge, BS-vs-textbook toggle, clause cross-links,
  worked-example "Load office block" demo button.

---

## 11. Decisions I made (flip any of these)

1. **Route C (single-joint), not a full sub-frame.** Lighter input, matches the textbook, and is
   code-sanctioned. Full sub-frame is out of scope.
2. **Compute moments as primary; keep manual entry as override.** Nothing regresses.
3. **`halve_beam_stiffness` defaults ON** (BS 8110-compliant) with a textbook toggle.
4. **3D scope = the spec in §7** (primitives + sprite labels), no new 3D deps, no CSS2DRenderer.
5. **Axial take-down is assist-not-authority:** auto-accumulate from slab pressure but let the
   student override `N` (matches cl 3.8.2.3 "beams simply supported" simplification).
