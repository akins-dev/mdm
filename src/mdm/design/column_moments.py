"""
Column design moments by BS 8110-1:1997 single-joint moment distribution (Route C).

This is the "moment engine" that turns a described sub-frame (the beams framing
into a column, and the column lifts above/below) into the four end moments
(Mx_top, Mx_bot, My_top, My_bot) that ``column.design_column_section`` needs.

Method (BS 8110 cl 3.2.1.2.5): at the single free joint (beam-column node) the
net unbalanced beam fixed-end moment is distributed *once*, with *no* carry-over,
to every member meeting at the joint in proportion to its stiffness. The far ends
of the beams are taken as fixed, so the beams are used at HALF their actual
stiffness (toggle ``halve_beam_stiffness``; Oyenuga's textbook uses full stiffness).

Reproduces the office-block worked example (Oyenuga Ch.7) to 3 s.f. — see
``tests/test_column_moments.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..models.beam import Span


# ---------------------------------------------------------------------------
# Step 2 — two-way slab -> equivalent beam UDL (for MOMENTS only, cl idealisation)
# ---------------------------------------------------------------------------
def slab_to_beam_udl(w: float, lx: float, ly: float, side: str = "short") -> float:
    """Equivalent UDL (kN/m) a two-way slab sheds onto a supporting beam.

    ``w`` = ultimate slab pressure (kN/m^2), ``lx`` = shorter slab span (m),
    ``ly`` = longer slab span (m). ``side`` = 'short' or 'long' beam.
        short-span beam:  w_eq = (1/3) * w * lx
        long-span  beam:  w_eq = (1/2) * w * lx * (1 - 1/(3 k^2)),  k = ly/lx
    """
    lx, ly = (lx, ly) if ly >= lx else (ly, lx)  # ensure lx is the shorter
    k = ly / lx if lx else 1.0
    if side == "short":
        return w * lx / 3.0
    return (w * lx / 2.0) * (1.0 - 1.0 / (3.0 * k * k))


def slab_beam_share(beam_span: float, perp_span: float, n: float) -> Tuple[float, Optional[dict]]:
    """UDL (kN/m) a *single* slab panel sheds onto one side of a beam.

    The panel is bounded by this beam (length ``beam_span``) and the perpendicular
    beam at the same joint (length ``perp_span``) — so the whole one-way/two-way
    question is decided by geometry we already have, no extra input. With
    ``lx = min`` (short side), ``ly = max`` (long side), ``k = ly/lx``:

      * ``k <= 2`` **two-way** — load sheds by 45deg yield lines:
          long-edge beam (the longer side) -> trapezoid  ``0.5 n lx (1 - 1/3k^2)``
          short-edge beam (the shorter side) -> triangle  ``(1/3) n lx``
      * ``k >  2`` **one-way** — slab spans the short way onto the two long-edge
        beams:  long-edge (supporting) beam -> ``0.5 n lx`` ; the short-edge beam
        runs parallel to the span and carries only a nominal strip (taken as 0).

    ``n`` = ultimate slab pressure (kN/m^2). Returns ``(w_share, detail)`` where
    ``detail`` (or ``None`` if no panel) carries every term for the calc sheet.
    """
    if beam_span <= 0 or perp_span <= 0 or n <= 0:
        return 0.0, None
    lx = min(beam_span, perp_span)
    ly = max(beam_span, perp_span)
    k = ly / lx
    long_edge = beam_span >= perp_span    # this beam runs along the panel's long side
    two_way = k <= 2.0
    if two_way and long_edge:
        share = 0.5 * n * lx * (1.0 - 1.0 / (3.0 * k * k))
        kind = "two-way, trapezoidal (long-edge beam)"
    elif two_way:
        share = n * lx / 3.0
        kind = "two-way, triangular (short-edge beam)"
    elif long_edge:
        share = 0.5 * n * lx
        kind = "one-way, supporting beam (spans onto it)"
    else:
        share = 0.0
        kind = "one-way, parallel beam (nominal, taken as 0)"
    detail = {"lx": lx, "ly": ly, "k": k, "two_way": two_way,
              "long_edge": long_edge, "kind": kind, "n": n,
              "perp_span": perp_span, "share": share}
    return share, detail


# ---------------------------------------------------------------------------
# Data model (what the student describes; see ARCHITECTURE_COLUMN.md sec.3)
# ---------------------------------------------------------------------------
@dataclass
class Beam:
    """A beam framing into the joint, in one bending plane of the column."""
    axis: str                       # 'x' | 'y'  -> contributes to Mx or My
    side: int                       # +1 | -1    -> opposite sides cancel
    span: float                     # m, centre-to-centre
    w: float                        # kN/m, total UDL on the beam
    b: float                        # mm, beam width
    h: float                        # mm, beam depth
    I_override: Optional[float] = None   # mm^4, for flanged (T/L) beams
    far_end_fixed: bool = True      # remote end fixed (cl 3.2.1.2.5)
    name: str = ""
    # Optional composition of ``w`` (for the calc sheet; total must equal ``w``).
    # Filled by ``build_column_frame`` when it derives the UDL from the slab; a
    # ``None`` breakdown means ``w`` was entered directly (manual override).
    load_breakdown: Optional[dict] = None

    @property
    def I(self) -> float:
        if self.I_override is not None:
            return self.I_override
        return self.b * self.h ** 3 / 12.0

    @property
    def fem(self) -> float:
        """Magnitude of the fixed-end moment (kNm) from the full-span UDL.

        Reuses ``Span.fixed_end_moments`` so partial UDLs / point loads can be
        supported later; for a full UDL this is simply w*L^2/12.
        """
        sp = Span("J", "F", self.span, udls=[(self.w, 0.0, self.span)])
        fem_left, _ = sp.fixed_end_moments()
        return abs(fem_left)

    def stiffness(self, halve: bool = True) -> float:
        """I/L (consistent mm units), halved if far-end-fixed and requested."""
        k = self.I / (self.span * 1000.0)
        return k * 0.5 if (halve and self.far_end_fixed) else k


@dataclass
class Lift:
    """One storey length of column (between two joints)."""
    name: str
    height: float                   # m, clear height  lo
    b: float                        # mm, column width  (dimension in 'y' plane)
    h: float                        # mm, column depth  (dimension in 'x' plane)
    cond_top: int = 1               # end conditions about x-x (Table 3.19/3.20)
    cond_bot: int = 1
    cond_top_y: int = 1             # end conditions about y-y (may differ per plane)
    cond_bot_y: int = 1

    def I(self, axis: str) -> float:
        # Bending about x uses depth h (I = b*h^3/12); about y uses width b.
        return self.b * self.h ** 3 / 12.0 if axis == "x" else self.h * self.b ** 3 / 12.0

    def stiffness(self, axis: str) -> float:
        return self.I(axis) / (self.height * 1000.0)


@dataclass
class Joint:
    """A beam-column node: the columns below/above it and the beams framing in."""
    name: str
    lift_below: Optional[Lift]
    lift_above: Optional[Lift]
    beams: List[Beam] = field(default_factory=list)
    N: float = 0.0                  # kN axial at this level (Step-1 take-down)


# ---------------------------------------------------------------------------
# Step 5/6 — the heart: single-joint distribution (no carry-over)
# ---------------------------------------------------------------------------
def single_joint_distribution(
    m_unbal: float, member_stiffnesses: Dict[str, float]
) -> Dict[str, float]:
    """Distribute an unbalanced moment to every member meeting at a joint.

    Each member takes  m_unbal * K_member / sum(K).  Beams and both columns are
    passed together; the caller reads off the column members' shares.
    """
    total = sum(member_stiffnesses.values())
    if total <= 0.0:
        return {name: 0.0 for name in member_stiffnesses}
    return {name: m_unbal * k / total for name, k in member_stiffnesses.items()}


def _classify(present_axes: set) -> str:
    if present_axes == {"x", "y"}:
        return "corner"
    if present_axes == {"x"}:
        return "edge-x"
    if present_axes == {"y"}:
        return "edge-y"
    return "internal"


# ---------------------------------------------------------------------------
# Steps 1-6 driver — a stack of joints -> four end moments per lift + a trace
# ---------------------------------------------------------------------------
def analyze_column_stack(
    joints: List[Joint], halve_beam_stiffness: bool = True
) -> Tuple[Dict[str, Dict[str, float]], List[dict]]:
    """Return ({lift_name: {Mx_top,Mx_bot,My_top,My_bot}}, trace).

    For each joint: build ONE joint stiffness sum over every member meeting there
    (both columns + all beams in both planes) — this lumped denominator is what
    Oyenuga's worked example and the research verification use. Then, per plane
    (x, y), the unbalanced moment is the signed sum of only *that plane's* beam
    FEMs (opposite sides cancel), and each column takes ``M_unbal * K_col / SigmaK``.
    The column-below share is the lift-below's top moment; the column-above share
    is the lift-above's foot moment.
    """
    results: Dict[str, Dict[str, float]] = {}

    def slot(lift: Lift) -> Dict[str, float]:
        return results.setdefault(
            lift.name, {"Mx_top": 0.0, "Mx_bot": 0.0, "My_top": 0.0, "My_bot": 0.0}
        )

    trace: List[dict] = []

    for joint in joints:
        # --- one lumped stiffness sum for every member at the joint ---
        members: Dict[str, float] = {}
        for i, bm in enumerate(joint.beams):
            members[f"beam{i}:{bm.name or bm.axis}{bm.side:+d}"] = bm.stiffness(halve_beam_stiffness)
        # Column stiffness is axis-dependent (rectangular section), so it is added
        # per axis below rather than lumped here.

        contributing_axes = set()
        for axis in ("x", "y"):
            beams_axis = [bm for bm in joint.beams if bm.axis == axis]
            if not beams_axis:
                continue
            net = sum(bm.side * bm.fem for bm in beams_axis)
            m_unbal = abs(net)
            if m_unbal > 1e-9:
                contributing_axes.add(axis)

            k_col_below = joint.lift_below.stiffness(axis) if joint.lift_below else 0.0
            k_col_above = joint.lift_above.stiffness(axis) if joint.lift_above else 0.0
            sumK = sum(members.values()) + k_col_below + k_col_above
            if sumK <= 0.0:
                continue

            m_below = m_unbal * k_col_below / sumK
            m_above = m_unbal * k_col_above / sumK

            if joint.lift_below is not None:
                slot(joint.lift_below)[f"M{axis}_top"] = m_below
            if joint.lift_above is not None:
                slot(joint.lift_above)[f"M{axis}_bot"] = m_above

            # Per-beam fixed-end moments in THIS plane (opposite sides cancel).
            fem_terms = [{
                "label": bm.name or f"{bm.axis}{bm.side:+d}",
                "w": bm.w, "span": bm.span, "side": bm.side, "fem": bm.fem,
                "load_breakdown": bm.load_breakdown, "_b": bm.b, "_h": bm.h,
            } for bm in beams_axis]

            # Stiffness of every member in the lumped denominator (both planes'
            # beams + both columns), each shown as k = I/L with the far-end-fixed
            # half-stiffness factor made explicit.
            beam_stiff = [{
                "label": bm.name or f"{bm.axis}{bm.side:+d}",
                "I": bm.I, "span": bm.span,
                "far_end_fixed": bm.far_end_fixed,
                "k": bm.stiffness(halve_beam_stiffness),
            } for bm in joint.beams]
            col_below = ({"I": joint.lift_below.I(axis), "L": joint.lift_below.height,
                          "k": k_col_below} if joint.lift_below is not None else None)
            col_above = ({"I": joint.lift_above.I(axis), "L": joint.lift_above.height,
                          "k": k_col_above} if joint.lift_above is not None else None)

            trace.append({
                "joint": joint.name,
                "axis": axis,
                "net_fem": net,
                "m_unbal": m_unbal,
                "fem_terms": fem_terms,
                "beam_stiff": beam_stiff,
                "col_below": col_below,
                "col_above": col_above,
                "halve": bool(halve_beam_stiffness),
                "beam_K": {k: round(v, 4) for k, v in members.items()},
                "K_col_below": round(k_col_below, 4),
                "K_col_above": round(k_col_above, 4),
                "sumK": round(sumK, 4),
                "M_col_below": m_below,
                "M_col_above": m_above,
            })

        trace.append({"joint": joint.name, "position": _classify(contributing_axes)})

    return results, trace
