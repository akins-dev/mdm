import math
from typing import List, Tuple, Dict, Any
from . import bs8110
from .design import row, money, fmt
from . import column_moments as cm

def calculate_strain_compatibility(
    N_des: float, 
    M_des: float, 
    b: float, 
    h: float, 
    fcu: float, 
    fy: float, 
    d: float, 
    d_prime: float
) -> float:
    """
    Numerically finds the required area of longitudinal steel (Asc) 
    using the rigorous strain compatibility method.
    Assumes symmetrical reinforcement: As = A's = Asc / 2
    """
    N = N_des * 1000.0
    M = M_des * 1e6

    max_asc = 0.08 * b * h
    
    gamma_m_c = 1.5
    gamma_m_s = 1.05
    
    Es = 200000.0
    
    best_asc = max_asc * 1.5
    found = False
    
    asc = 0.0
    step = (0.001 * b * h) # 0.1% increments
    
    while asc <= max_asc:
        As = asc / 2.0
        Asc_prime = asc / 2.0
        
        x_low = 1e-5
        x_high = h * 2.0 
        
        x = h / 2.0
        N_cap = 0.0
        M_cap = 0.0
        
        for _ in range(50):
            x = (x_low + x_high) / 2.0
            
            strain_cu = 0.0035
            
            s = 0.9 * x
            if s > h:
                s = h
            
            Fc = 0.67 * fcu / gamma_m_c * b * s
            
            strain_sc = strain_cu * (x - d_prime) / x
            strain_s = strain_cu * (d - x) / x 
            
            f_sc = strain_sc * Es
            fy_design = fy / gamma_m_s
            if f_sc > fy_design:
                f_sc = fy_design
            elif f_sc < -fy_design:
                f_sc = -fy_design
                
            f_s = strain_s * Es
            if f_s > fy_design:
                f_s = fy_design
            elif f_s < -fy_design:
                f_s = -fy_design
                
            Fsc = f_sc * Asc_prime
            Fs = f_s * As
            
            N_cap = Fc + Fsc - Fs
            
            if N_cap > N:
                x_high = x
            else:
                x_low = x
                
        s = 0.9 * x
        if s > h:
            s = h
            
        Mc = Fc * (h/2.0 - s/2.0)
        Msc = Fsc * (h/2.0 - d_prime)
        Ms = Fs * (d - h/2.0)
        
        M_cap = Mc + Msc + Ms
        
        if M_cap >= M:
            best_asc = asc
            found = True
            break
            
        asc += step
        
    if not found:
        return float('inf') 
        
    return best_asc

def _design_moment_axis(m_top: float, m_bot: float, emin: float, N: float,
                        madd: float = 0.0) -> Tuple[float, float, float, float, float]:
    """BS 8110 cl 3.8.3.2 design moment (kNm) about one axis.

    ``m_top``/``m_bot`` are the signed initial end moments; the column is in
    double curvature (M1 negative) when their signs differ. Returns the design
    moment = greatest of {M2, Mi+Madd, M1+Madd/2, N*emin} together with the
    intermediate M1, M2, Mi, Mmin for the calc sheet.
    """
    m2 = max(abs(m_top), abs(m_bot))
    m1_mag = min(abs(m_top), abs(m_bot))
    double_curv = (m_top * m_bot) < 0.0
    m1 = -m1_mag if double_curv else m1_mag
    mi = max(0.4 * m1 + 0.6 * m2, 0.4 * m2)
    m_min = N * emin / 1000.0
    m_des = max(m2, mi + madd, m1 + madd / 2.0, m_min)
    return m_des, m1, m2, mi, m_min


def _additional_moment(le: float, dim: float, N: float, K: float) -> Tuple[float, float, float]:
    """cl 3.8.3.1 additional (slender) moment (kNm) about one axis.

    ``le`` and ``dim`` in mm; ``dim`` is the section depth in the plane of
    bending (h for the x-x axis, b for the y-y axis) — consistent with the
    le/dim slenderness ratio. Returns (Madd, beta_a, au).
    """
    beta_a = (le / dim) ** 2 / 2000.0
    au = beta_a * K * dim
    return N * au / 1000.0, beta_a, au


def _k_factor(N: float, Nuz: float, Nbal: float) -> float:
    """cl 3.8.3.1 reduction factor K = (Nuz-N)/(Nuz-Nbal), clamped to [0, 1]."""
    if Nuz <= Nbal:
        return 1.0
    return max(0.0, min(1.0, (Nuz - N) / (Nuz - Nbal)))


def _resolve_biaxial(N: float, Mx: float, My: float, Mmin_x: float, Mmin_y: float,
                     b: float, h: float, fcu: float):
    """cl 3.8.4.5 biaxial -> equivalent uniaxial moment.

    Returns (M_des, design_b, design_h, axis_str, is_biaxial, beta, calc_str).
    Biaxial only when real moment (beyond min-ecc) exists about BOTH axes.
    """
    is_biaxial = abs(Mx) > Mmin_x + 1e-5 and abs(My) > Mmin_y + 1e-5
    if is_biaxial:
        beta = bs8110.biaxial_beta(N / (b * h * fcu))  # Table 3.22
        if (Mx / h) >= (My / b):
            m = Mx + beta * (h / b) * My
            calc = (f"\\( \\beta = {money(beta)} \\)<br/>\\( \\frac{{M_x}}{{h}} \\ge "
                    f"\\frac{{M_y}}{{b}} \\Rightarrow M'_x = M_x + \\beta \\frac{{h}}{{b}} M_y "
                    f"= {money(m)} \\text{{ kNm}} \\)")
            return m, b, h, "Biaxial \\( \\rightarrow \\) Equivalent Uniaxial X-X", True, beta, calc
        m = My + beta * (b / h) * Mx
        calc = (f"\\( \\beta = {money(beta)} \\)<br/>\\( \\frac{{M_y}}{{b}} > "
                f"\\frac{{M_x}}{{h}} \\Rightarrow M'_y = M_y + \\beta \\frac{{b}}{{h}} M_x "
                f"= {money(m)} \\text{{ kNm}} \\)")
        return m, h, b, "Biaxial \\( \\rightarrow \\) Equivalent Uniaxial Y-Y", True, beta, calc
    if Mx >= My:
        return Mx, b, h, "Uniaxial X-X", False, 1.0, ""
    return My, h, b, "Uniaxial Y-Y", False, 1.0, ""


def design_column_section(
    b: float,
    h: float,
    l0: float,
    is_braced: bool,
    cond_top: int,
    cond_bot: int,
    N: float,
    Mx_top: float,
    Mx_bot: float,
    My_top: float,
    My_bot: float,
    fcu: float,
    fy: float,
    cover: float,
    target_dia: float
) -> str:
    """Backwards-compatible string API (used by the /design_column override)."""
    html, _summary = _design_column(
        b, h, l0, is_braced, cond_top, cond_bot, N,
        Mx_top, Mx_bot, My_top, My_bot, fcu, fy, cover, target_dia)
    return html


def _design_column(
    b: float,
    h: float,
    l0: float,
    is_braced: bool,
    cond_top: int,
    cond_bot: int,
    N: float,
    Mx_top: float,
    Mx_bot: float,
    My_top: float,
    My_bot: float,
    fcu: float,
    fy: float,
    cover: float,
    target_dia: float,
    cond_top_y: Optional[int] = None,
    cond_bot_y: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Full column design. Returns (calc-sheet HTML, structured summary).

    ``summary`` feeds the 3D visualisation / HUD: section, design forces, the
    chosen bars, a section utilisation (Asc_req / 6% cap) and a status flag.
    ``cond_*_y`` default to the x-x conditions when not supplied (square-frame /
    override path); when they differ, ``l_ey`` uses its own beta (Table 3.19/3.20).
    """
    cond_top_y = cond_top if cond_top_y is None else cond_top_y
    cond_bot_y = cond_bot if cond_bot_y is None else cond_bot_y
    summary: Dict[str, Any] = {
        "b": b, "h": h, "N": N, "M_des": 0.0, "axis": "", "slender": False,
        "le_h": 0.0, "le_b": 0.0, "bars": "", "Asc_req": 0.0, "Asc_prov": 0.0,
        "links": "", "utilisation": 0.0, "status": "ok",
    }
    html_lines = []
    html_lines.append("<div class='calc-sheet'>")
    html_lines.append("<h4>Column Design to BS 8110-1:1997</h4>")
    
    html_lines.append(row(
        "Geometry",
        f"<h3 class='calc-section-title'>Section Properties</h3><p>\\( b = {fmt(b)} \\text{{ mm}} \\)<br/>\\( h = {fmt(h)} \\text{{ mm}} \\)<br/>\\( l_0 = {fmt(l0)} \\text{{ m}} \\)</p>",
        f"\\( b = {fmt(b)} \\text{{ mm}} \\)<br/>\\( h = {fmt(h)} \\text{{ mm}} \\)"
    ))
    
    beta_x = bs8110.beta_effective_length(is_braced, cond_top, cond_bot)     # x-x
    beta_y = bs8110.beta_effective_length(is_braced, cond_top_y, cond_bot_y)  # y-y

    lex = beta_x * l0 * 1000
    ley = beta_y * l0 * 1000

    ratio_x = lex / h
    ratio_y = ley / b

    limit = 15 if is_braced else 10

    is_slender = ratio_x > limit or ratio_y > limit
    slender_str = "<b>SLENDER COLUMN</b>" if is_slender else "<b>SHORT COLUMN</b>"
    summary["slender"] = is_slender
    summary["le_h"] = round(ratio_x, 2)
    summary["le_b"] = round(ratio_y, 2)

    html_lines.append(row(
        "Clause 3.8.1.3<br/>Clause 3.8.1.6",
        f"<h3 class='calc-section-title'>Effective Length & Slenderness</h3><p>"
        f"\\( \\beta_x = {fmt(beta_x)} \\) (cond {cond_top}/{cond_bot}), "
        f"\\( \\beta_y = {fmt(beta_y)} \\) (cond {cond_top_y}/{cond_bot_y})<br/>"
        f"\\( l_{{ex}} = \\beta_x l_0 = {fmt(lex)} \\text{{ mm}} \\), "
        f"\\( l_{{ey}} = \\beta_y l_0 = {fmt(ley)} \\text{{ mm}} \\)<br/>"
        f"\\( l_{{ex}}/h = {fmt(ratio_x)} \\)<br/>\\( l_{{ey}}/b = {fmt(ratio_y)} \\)</p>",
        slender_str
    ))
    
    emin_x = min(0.05 * h, 20.0)
    emin_y = min(0.05 * b, 20.0)

    Mmin_x = N * emin_x / 1000.0
    Mmin_y = N * emin_y / 1000.0

    html_lines.append(row(
        "Clause 3.8.2.4",
        f"<h3 class='calc-section-title'>Minimum Eccentricity</h3><p>\\( e_{{min,x}} = \\min(0.05h, 20) = {fmt(emin_x)} \\text{{ mm}} \\)<br/>\\( e_{{min,y}} = \\min(0.05b, 20) = {fmt(emin_y)} \\text{{ mm}} \\)<br/>\\( M_{{min,x}} = N \\times e_{{min,x}} = {money(Mmin_x)} \\text{{ kNm}} \\)<br/>\\( M_{{min,y}} = N \\times e_{{min,y}} = {money(Mmin_y)} \\text{{ kNm}} \\)</p>",
        f"\\( M_{{min,x}} = {money(Mmin_x)} \\text{{ kNm}} \\)<br/>\\( M_{{min,y}} = {money(Mmin_y)} \\text{{ kNm}} \\)"
    ))

    # Initial design moments (cl 3.8.3.2 ladder, no additional moment yet).
    Mx, M1x, M2x, Mix, _ = _design_moment_axis(Mx_top, Mx_bot, emin_x, N)
    My, M1y, M2y, Miy, _ = _design_moment_axis(My_top, My_bot, emin_y, N)

    link_dia = 10.0

    if is_slender:
        # K depends on Asc (via Nuz), so estimate Asc from a provisional design
        # that excludes the additional moment, then compute K and Madd once.
        Mp, pb, ph, _, _, _, _ = _resolve_biaxial(N, Mx, My, Mmin_x, Mmin_y, b, h, fcu)
        d_prov = ph - cover - link_dia - (target_dia / 2.0)
        d_pr_prime = cover + link_dia + (target_dia / 2.0)
        Asc_prov = calculate_strain_compatibility(N, Mp, pb, ph, fcu, fy, d_prov, d_pr_prime)
        if Asc_prov == float('inf'):
            Asc_prov = 0.06 * b * h
        Nuz = (0.45 * fcu * b * h + 0.95 * fy * Asc_prov) / 1000.0
        d_bal = h - cover - link_dia - (target_dia / 2.0)
        Nbal = 0.25 * fcu * b * d_bal / 1000.0
        K = _k_factor(N, Nuz, Nbal)

        Madd_x, beta_a_x, au_x = _additional_moment(lex, h, N, K)
        Madd_y, beta_a_y, au_y = _additional_moment(ley, b, N, K)

        Mx, M1x, M2x, Mix, _ = _design_moment_axis(Mx_top, Mx_bot, emin_x, N, Madd_x)
        My, M1y, M2y, Miy, _ = _design_moment_axis(My_top, My_bot, emin_y, N, Madd_y)

        html_lines.append(row(
            "Clause 3.8.3.1",
            f"<h3 class='calc-section-title'>Additional Moments (Slender)</h3><p>\\( N_{{uz}} = {money(Nuz)} \\text{{ kN}}, N_{{bal}} = {money(Nbal)} \\text{{ kN}}, K = {money(K)} \\)<br/>\\( \\beta_{{a,x}} = {money(beta_a_x)}, a_{{u,x}} = {fmt(au_x)} \\text{{ mm}}, M_{{add,x}} = {money(Madd_x)} \\text{{ kNm}} \\)<br/>\\( \\beta_{{a,y}} = {money(beta_a_y)}, a_{{u,y}} = {fmt(au_y)} \\text{{ mm}}, M_{{add,y}} = {money(Madd_y)} \\text{{ kNm}} \\)</p>",
            f"\\( M_x = {money(Mx)} \\text{{ kNm}} \\)<br/>\\( M_y = {money(My)} \\text{{ kNm}} \\)"
        ))
    
    M_des, design_b, design_h, axis_str, is_biaxial, _, calc_str = _resolve_biaxial(
        N, Mx, My, Mmin_x, Mmin_y, b, h, fcu)
    summary["M_des"] = round(M_des, 2)
    summary["axis"] = axis_str

    if is_biaxial:
        html_lines.append(row(
            "Clause 3.8.4.5",
            f"<h3 class='calc-section-title'>Biaxial Bending</h3><p>{calc_str}</p>",
            axis_str
        ))
    else:
        html_lines.append(row(
            "Clause 3.8.4.3",
            f"<h3 class='calc-section-title'>Design Forces</h3><p>\\( N = {money(N)} \\text{{ kN}} \\)<br/>\\( M_{{des}} = {money(M_des)} \\text{{ kNm}} \\)</p>",
            axis_str
        ))

    d_eff = design_h - cover - link_dia - (target_dia / 2.0)
    d_prime = cover + link_dia + (target_dia / 2.0)
    
    Asc_req = calculate_strain_compatibility(N, M_des, design_b, design_h, fcu, fy, d_eff, d_prime)
    
    if Asc_req == float('inf'):
        html_lines.append(row(
            "",
            f"<h3 class='calc-section-title'>Main Reinforcement</h3><p class='text-danger'>Section is inadequate to carry the design forces. Increase section dimensions or concrete strength.</p>",
            "SECTION INADEQUATE",
            "danger"
        ))
        html_lines.append("</div>")
        summary["status"] = "inadequate"
        summary["utilisation"] = 1.5
        summary["bars"] = "INADEQUATE"
        return "".join(html_lines), summary

    Asc_min = 0.004 * b * h
    if Asc_req < Asc_min:
        Asc_req = Asc_min

    Asc_max = 0.06 * b * h
    if Asc_req > Asc_max:
        html_lines.append(row(
            "Clause 3.12.6.2",
            f"<h3 class='calc-section-title'>Main Reinforcement</h3><p>\\( A_{{sc}} = {money(Asc_req)} \\text{{ mm}}^2 \\)<br/><span class='text-danger'>Exceeds maximum allowable steel 6% ({money(Asc_max)} mm²).</span></p>",
            "SECTION INADEQUATE",
            "danger"
        ))
        html_lines.append("</div>")
        summary["status"] = "inadequate"
        summary["utilisation"] = 1.5
        summary["Asc_req"] = round(Asc_req, 0)
        summary["bars"] = "INADEQUATE"
        return "".join(html_lines), summary
        
    bar_counts = [4, 6, 8, 10, 12]
    dias = [16, 20, 25, 32]
    if target_dia in dias:
        dias.remove(int(target_dia))
        dias.insert(0, int(target_dia))
        
    selected_count = 0
    selected_dia = 0
    selected_area = 0.0
    
    for dia in dias:
        for c in bar_counts:
            a = c * math.pi * (dia**2) / 4.0
            if a >= Asc_req:
                selected_count = c
                selected_dia = dia
                selected_area = a
                break
        if selected_count > 0:
            break
            
    if selected_count == 0:
        html_lines.append(row(
            "",
            f"<h3 class='calc-section-title'>Main Reinforcement</h3><p class='text-danger'>Unable to find suitable bar arrangement.</p>",
            "FAIL",
            "danger"
        ))
        html_lines.append("</div>")
        summary["status"] = "inadequate"
        summary["utilisation"] = 1.5
        summary["bars"] = "FAIL"
        return "".join(html_lines), summary

    html_lines.append(row(
        "Strain Compatibility<br/>Table 3.25",
        f"<h3 class='calc-section-title'>Main Reinforcement</h3><p>Required \\( A_{{sc}} = {money(Asc_req)} \\text{{ mm}}^2 \\)<br/>Provide {selected_count}H{selected_dia} \\( (A_{{sc,prov}} = {money(selected_area)} \\text{{ mm}}^2) \\)</p>",
        f"Provide {selected_count}H{selected_dia}",
        "success"
    ))

    sv_max = min(12 * selected_dia, design_b, design_h)
    html_lines.append(row(
        "Clause 3.12.7.1",
        f"<h3 class='calc-section-title'>Transverse Links</h3><p>Link spacing \\( s_v \\le 12 \\times \\phi \\)<br/>\\( s_v \\le 12 \\times {selected_dia} = {12 * selected_dia} \\text{{ mm}} \\)</p>",
        f"Provide H{int(link_dia)} @ {fmt(sv_max)} c/c",
        "success"
    ))

    html_lines.append("</div>")
    summary["Asc_req"] = round(Asc_req, 0)
    summary["Asc_prov"] = round(selected_area, 0)
    summary["bars"] = f"{selected_count}H{selected_dia}"
    summary["links"] = f"H{int(link_dia)} @ {fmt(sv_max)} c/c"
    # Utilisation vs the 6% steel cap (a proxy for how hard the section works).
    summary["utilisation"] = round(min(1.2, Asc_req / Asc_max), 3) if Asc_max else 0.0
    summary["status"] = "ok"
    return "".join(html_lines), summary


# ---------------------------------------------------------------------------
# Phase 2 orchestration: frame description -> moments -> design (per lift)
# ---------------------------------------------------------------------------
def _beam_from_payload(spec: dict) -> cm.Beam:
    """Build a column_moments.Beam from a JSON beam spec.

    The FEM UDL is normally *derived* (slab share + self-weight + wall) in
    ``build_column_frame`` once all beams at the joint are known. A non-zero
    ``w`` here is treated as a manual override and left untouched. The wall line
    load (kN/m) and the override flag are stashed on the beam for that step.
    """
    w = spec.get("w")
    manual = w not in (None, "", 0)
    if not manual and spec.get("slab_w") not in (None, "", 0):
        # Legacy direct slab-panel entry (lx/ly typed) — still honoured.
        w = cm.slab_to_beam_udl(
            float(spec["slab_w"]), float(spec.get("lx", 0) or 0),
            float(spec.get("ly", 0) or 0), spec.get("slab_side", "short"))
        manual = True
    bm = cm.Beam(
        axis=str(spec.get("axis", "x")),
        side=int(spec.get("side", 1)),
        span=float(spec.get("span", 0) or 0),
        w=float(w or 0),
        b=float(spec.get("b", 300) or 300),
        h=float(spec.get("h", 600) or 600),
        I_override=(float(spec["I_override"]) if spec.get("I_override") not in (None, "", 0) else None),
        far_end_fixed=bool(spec.get("far_end_fixed", True)),
        name=str(spec.get("name", "")),
    )
    # Stashed for the load-composition step (not part of the moment engine).
    bm.wall = float(spec.get("wall", 0) or 0)
    bm.manual_w = manual
    return bm


def _compose_beam_loads(beams: List["cm.Beam"], area_load: float, is_roof: bool) -> None:
    """Set each beam's FEM UDL from slab share + self-weight + wall.

    ``w_total = w_slab + w_selfwt + w_wall`` — unless a manual ``w`` was entered,
    in which case it is kept verbatim. Roof beams (top storey) carry no wall load
    (roof slab + beam self-weight only). The slab share is derived per panel from
    the perpendicular beam spans at the joint (see ``cm.slab_beam_share``); every
    term is stored on ``bm.load_breakdown`` so the calc sheet can show its origin.
    """
    for bm in beams:
        other = "y" if bm.axis == "x" else "x"
        perp = [(o.side, o.span) for o in beams if o.axis == other and o.span > 0]
        w_slab = 0.0
        slab_terms = []
        for side, p in perp:
            share, detail = cm.slab_beam_share(bm.span, p, area_load)
            if detail is not None:
                detail["side"] = side
                slab_terms.append(detail)
                w_slab += share
        w_selfwt = (bm.b / 1000.0) * (bm.h / 1000.0) * 24.0 * 1.4  # factored s/w
        w_wall = 0.0 if is_roof else float(getattr(bm, "wall", 0.0) or 0.0)
        manual = bool(getattr(bm, "manual_w", False))
        if not manual:
            bm.w = w_slab + w_selfwt + w_wall
        bm.load_breakdown = {
            "manual": manual, "w_slab": w_slab, "w_selfwt": w_selfwt,
            "w_wall": w_wall, "is_roof": is_roof, "total": bm.w,
            "area_load": area_load, "slab_terms": slab_terms,
        }


def _derive_end_condition(beams: List["cm.Beam"], axis: str, col_dim: float,
                          braced: bool, top_of_roof: bool) -> dict:
    """End condition (1-3, or 4 unbraced free) for one column end in one plane.

    Restraint about an axis comes from the beams framing in *in that plane*
    (``axis``) compared with the column dimension in that plane (``col_dim`` =
    ``h`` for x-x, ``b`` for y-y), per BS 8110 Table 3.19/3.20 definitions:

      * cond 1 - monolithic beams **both sides**, each **at least as deep** as the
        column dimension in the plane;
      * cond 2 - beams present but shallower, or on one side only (edge/corner);
      * cond 3 - no beam in this plane (slab / nominal restraint only);
      * cond 4 - unrestrained free end (unbraced roof with no beam).
    """
    inplane = [b for b in beams if b.axis == axis and b.span > 0]
    if not inplane:
        cond = 4 if (top_of_roof and not braced) else 3
        return {"cond": cond, "deep": False, "both": False,
                "max_depth": 0.0, "col_dim": col_dim, "n_beams": 0}
    both = any(b.side > 0 for b in inplane) and any(b.side < 0 for b in inplane)
    max_depth = max(b.h for b in inplane)
    deep = max_depth >= col_dim
    cond = 1 if (deep and both) else 2
    return {"cond": cond, "deep": deep, "both": both,
            "max_depth": max_depth, "col_dim": col_dim, "n_beams": len(inplane)}


def _derive_all_end_conditions(lifts, beams_per_level, braced: bool, base_fixity: int):
    """Set each lift's per-plane end conditions from the frame; return trace rows.

    Storeys are bottom->top; the joint on TOP of storey ``i`` carries
    ``beams_per_level[i]``. So a lift's TOP end sees its own storey's beams and
    its BOTTOM end sees the storey-below's beams. The very bottom end connects to
    the foundation and uses the ``base_fixity`` override (default 1, fixed base).
    """
    n = len(lifts)
    rows = []
    for i, lift in enumerate(lifts):
        top_of_roof = (i == n - 1)
        tx = _derive_end_condition(beams_per_level[i], "x", lift.h, braced, top_of_roof)
        ty = _derive_end_condition(beams_per_level[i], "y", lift.b, braced, top_of_roof)
        if i == 0:
            base = {"cond": base_fixity, "base": True, "col_dim": lift.h}
            bx = by = base
        else:
            bx = _derive_end_condition(beams_per_level[i - 1], "x", lift.h, braced, False)
            by = _derive_end_condition(beams_per_level[i - 1], "y", lift.b, braced, False)
        lift.cond_top = tx["cond"]
        lift.cond_bot = bx["cond"]
        lift.cond_top_y = ty["cond"]
        lift.cond_bot_y = by["cond"]
        rows.append({"name": lift.name, "top_x": tx, "top_y": ty,
                     "bot_x": bx, "bot_y": by, "base": (i == 0)})
    return rows


def _tributary_terms(beams: List["cm.Beam"]) -> dict:
    """Tributary width/depth for a joint, DERIVED from the beams framing in.

    Each beam carries half its span to the adjacent column, so the tributary
    dimension in a plane is 0.5*(span on the + side) + 0.5*(span on the - side).
    A missing beam (corner/edge column) contributes 0. Returns the per-side spans
    too, so the derivation can be shown step-by-step (no obscure origins).
    """
    def span_on(axis: str, side: int) -> float:
        vals = [bm.span for bm in beams if bm.axis == axis and bm.side == side]
        return max(vals) if vals else 0.0

    sx_p, sx_m = span_on("x", 1), span_on("x", -1)
    sy_p, sy_m = span_on("y", 1), span_on("y", -1)
    return {
        "sx_p": sx_p, "sx_m": sx_m, "sy_p": sy_p, "sy_m": sy_m,
        "trib_x": 0.5 * sx_p + 0.5 * sx_m,
        "trib_y": 0.5 * sy_p + 0.5 * sy_m,
    }


def build_column_frame(payload: dict):
    """Return (joints, lifts, globals, axial_html, cond_rows) from a payload.

    `storeys` are ordered bottom -> top. Each storey's `beams` frame in at the
    joint on TOP of that storey. The beam FEM UDLs are DERIVED (slab share +
    self-weight + wall; roof = slab + self-weight only), the axial load N is
    calculated rigorously top-down with tributary widths DERIVED from beam spans,
    and the end conditions (Table 3.19/3.20) are DERIVED per plane from the beam
    depths vs the column dimension. Nothing structural is hand-typed.
    """
    g = payload.get("global", payload)
    storeys = payload.get("storeys", [])
    braced = bool(g.get("braced", True))
    base_fixity = int(g.get("base_fixity", 1) or 1)
    lifts: List[cm.Lift] = []
    beams_per_level: List[List[cm.Beam]] = []
    N_per_level: List[float] = []
    for s in storeys:
        lifts.append(cm.Lift(
            name=str(s.get("name", f"L{len(lifts)+1}")),
            height=float(s.get("height", 3.0)),
            b=float(s.get("b", g.get("b", 300))),
            h=float(s.get("h", g.get("h", 400))),
        ))
        beams_per_level.append([_beam_from_payload(bs) for bs in s.get("beams", [])])
        N_per_level.append(float(s.get("N", 0) or 0))

    # --- COMPOSE BEAM FEM LOADS (slab share + self-weight + wall) ---
    # The top storey is the roof: its beams carry roof slab + self-weight, no wall.
    n_st = len(storeys)
    for i, s in enumerate(storeys):
        _compose_beam_loads(beams_per_level[i], float(s.get("area_load", 0) or 0),
                            is_roof=(i == n_st - 1))

    # --- DERIVE END CONDITIONS (Table 3.19/3.20) from the frame geometry ---
    cond_rows = _derive_all_end_conditions(lifts, beams_per_level, braced, base_fixity)

    # --- TRIBUTARY AXIAL LOAD TAKEDOWN (tributary derived from beam spans) ---
    # Does any storey describe beams? If not, there is no frame to take load from.
    any_beams = any(beams_per_level)

    axial_html = []
    if any_beams:
        axial_html.append("<div class='calc-sheet'>")
        axial_html.append("<h4>Axial Load Take-down (Tributary Area Method)</h4>")
        axial_html.append(
            "<p style='font-size:12px;color:#64748b'>Each beam carries half its span to the "
            "adjacent column, so the tributary width in a plane is "
            "\\( \\tfrac12 (\\text{span}_+ + \\text{span}_-) \\). "
            "\\( A_t = L_{tx}\\,L_{ty} \\), \\( L_t = L_{tx} + L_{ty} \\).</p>")
        N_cumulative = 0.0
        n = len(lifts)
        # Calculate top-down (index n-1 down to 0)
        for i in range(n - 1, -1, -1):
            s = storeys[i]
            lift = lifts[i]
            beams = beams_per_level[i]
            area_load = float(s.get("area_load", 0))
            line_load = float(s.get("line_load", 0))

            t = _tributary_terms(beams)
            trib_x, trib_y = t["trib_x"], t["trib_y"]
            At = trib_x * trib_y
            Lt = trib_x + trib_y

            slab_N = At * area_load
            beam_N = Lt * line_load
            vol = (lift.b / 1000.0) * (lift.h / 1000.0) * lift.height
            col_weight = vol * 24.0 * 1.4  # factored concrete self-weight (1.4 x 24 kN/m^3)

            storey_N = slab_N + beam_N + col_weight
            N_cumulative += storey_N
            N_per_level[i] = N_cumulative

            if At <= 0 and (area_load or line_load):
                trib_note = ("<br/><span class='text-danger'>No beams described at this level "
                             "&rarr; tributary = 0, so slab/line loads are not applied. Add beams "
                             "or use Direct Moments.</span>")
            else:
                trib_note = ""

            axial_html.append(row(
                "Tributary Loads",
                f"<h3 class='calc-section-title'>{lift.name} Takedown</h3>"
                f"<p>Load from above: \\( {money(N_cumulative - storey_N)} \\text{{ kN}} \\)<br/>"
                f"Trib width: \\( L_{{tx}} = \\tfrac12({fmt(t['sx_p'])} + {fmt(t['sx_m'])}) = {fmt(trib_x)} \\text{{ m}} \\), "
                f"\\( L_{{ty}} = \\tfrac12({fmt(t['sy_p'])} + {fmt(t['sy_m'])}) = {fmt(trib_y)} \\text{{ m}} \\)<br/>"
                f"\\( A_t = {fmt(trib_x)} \\times {fmt(trib_y)} = {fmt(At)} \\text{{ m}}^2 \\), "
                f"\\( L_t = {fmt(trib_x)} + {fmt(trib_y)} = {fmt(Lt)} \\text{{ m}} \\)<br/>"
                f"Slab Load: \\( {fmt(At)} \\text{{ m}}^2 \\times {fmt(area_load)} \\text{{ kN/m}}^2 = {money(slab_N)} \\text{{ kN}} \\)<br/>"
                f"Beam/Wall Load: \\( {fmt(Lt)} \\text{{ m}} \\times {fmt(line_load)} \\text{{ kN/m}} = {money(beam_N)} \\text{{ kN}} \\)<br/>"
                f"Col Self-weight: \\( ({fmt(lift.b/1000)} \\times {fmt(lift.h/1000)} \\times {fmt(lift.height)}) \\times 24 \\times 1.4 = {money(col_weight)} \\text{{ kN}} \\)"
                f"{trib_note}</p>",
                f"\\( N = {money(N_cumulative)} \\text{{ kN}} \\)"
            ))

        axial_html.append("</div>")

    joints: List[cm.Joint] = []
    n = len(lifts)
    for i in range(n):
        joints.append(cm.Joint(
            name=lifts[i].name,
            lift_below=lifts[i],
            lift_above=lifts[i + 1] if i + 1 < n else None,
            beams=beams_per_level[i],
            N=N_per_level[i],
        ))
    return joints, lifts, g, "".join(axial_html), cond_rows


def _grp(v: float) -> str:
    """Group-separated integer for large section values (mm^3, mm^4)."""
    return f"{v:,.0f}"


def _load_breakdown_html(t: dict) -> str:
    """Show how a beam's UDL was composed: slab share + self-wt + wall = w."""
    lb = t.get("load_breakdown")
    if not lb:
        return ""
    if lb.get("manual"):
        return (f"\\( \\;\\; w = {fmt(t['w'])}\\text{{ kN/m}} \\) "
                "<span style='color:#64748b'>(entered directly)</span><br/>")
    parts = ["<span style='color:#475569; font-size:12px;'>Load build-up: "]
    for d in lb.get("slab_terms", []):
        classify = d["kind"]
        parts.append(
            f"<br/>&nbsp;&nbsp;slab panel ({fmt(d['perp_span'])} m perp.): "
            f"\\( k=\\tfrac{{{fmt(d['ly'])}}}{{{fmt(d['lx'])}}}={fmt(d['k'])} \\) "
            f"&rarr; <i>{classify}</i>, "
            f"\\( w={fmt(d['share'])}\\text{{ kN/m}} \\)")
    parts.append(
        f"<br/>&nbsp;&nbsp;\\( w_{{slab}}={fmt(lb['w_slab'])} \\), "
        f"\\( w_{{s/w}}=\\tfrac{{{fmt(t.get('_b', 0))}\\times{fmt(t.get('_h', 0))}}}{{10^6}}"
        f"\\times24\\times1.4={fmt(lb['w_selfwt'])} \\), "
        f"\\( w_{{wall}}={fmt(lb['w_wall'])} \\)"
        + (" <i>(roof: no wall)</i>" if lb.get("is_roof") else "")
        + f" \\( \\Rightarrow w={fmt(lb['total'])}\\text{{ kN/m}} \\)</span><br/>")
    return "".join(parts)


def _fem_step(e: dict) -> str:
    """Step 1 body: each beam's fixed-end moment and the signed sum."""
    lines = ["<b>Step 1 — Fixed-end moments</b> (beams framing in, this plane; "
             "opposite sides cancel)<br/>"]
    term_strs = []
    for t in e["fem_terms"]:
        sign = "+" if t["side"] >= 0 else "-"
        lines.append(_load_breakdown_html(t))
        lines.append(
            f"\\( \\text{{{t['label']}}}:\\; FEM = \\dfrac{{w L^2}}{{12}} "
            f"= \\dfrac{{{fmt(t['w'])} \\times {fmt(t['span'])}^2}}{{12}} "
            f"= {money(t['fem'])}\\text{{ kNm}}\\;({sign}) \\)<br/>")
        term_strs.append(f"({sign}{money(t['fem'])})")
    joined = " ".join(term_strs) if term_strs else "0"
    lines.append(
        f"\\( \\Sigma FEM = {joined} = {money(e['net_fem'])} "
        f"\\Rightarrow M_{{unbal}} = {money(e['m_unbal'])}\\text{{ kNm}} \\)")
    return "".join(lines)


def _stiffness_step(e: dict) -> str:
    """Step 2 body: k = I/L for every member, halved for far-end-fixed beams."""
    lines = ["<b>Step 2 — Member stiffnesses</b> \\( k = I/L \\) "
             "(beams at \\( \\tfrac12 k \\), far end fixed — cl 3.2.1.2.5)<br/>"]
    for t in e["beam_stiff"]:
        L_mm = t["span"] * 1000.0
        halved = e["halve"] and t["far_end_fixed"]
        half = "\\tfrac12 \\cdot " if halved else ""
        note = "\\;(\\text{far end fixed})" if halved else ""
        lines.append(
            f"\\( k_{{\\text{{{t['label']}}}}} = {half}\\dfrac{{I}}{{L}} "
            f"= {half}\\dfrac{{{_grp(t['I'])}}}{{{_grp(L_mm)}}} "
            f"= {_grp(t['k'])}\\text{{ mm}}^3{note} \\)<br/>")
    for name, d in (("below", e["col_below"]), ("above", e["col_above"])):
        if not d:
            continue
        L_mm = d["L"] * 1000.0
        lines.append(
            f"\\( k_{{col,{name}}} = \\dfrac{{I}}{{L}} "
            f"= \\dfrac{{{_grp(d['I'])}}}{{{_grp(L_mm)}}} "
            f"= {_grp(d['k'])}\\text{{ mm}}^3 \\)<br/>")
    lines.append(
        f"\\( \\Sigma K = k_{{col,below}} + k_{{col,above}} + \\Sigma k_{{beam}} "
        f"= {_grp(e['K_col_below'])} + {_grp(e['K_col_above'])} + "
        f"{_grp(e['sumK'] - e['K_col_below'] - e['K_col_above'])} "
        f"= {_grp(e['sumK'])}\\text{{ mm}}^3 \\)")
    return "".join(lines)


def _distribution_step(e: dict) -> str:
    """Step 3 body: the single-joint distribution (no carry-over)."""
    return (
        "<b>Step 3 — Single-joint distribution</b> (no carry-over)<br/>"
        f"\\( M_{{col,below}} = M_{{unbal}}\\dfrac{{k_{{col,below}}}}{{\\Sigma K}} "
        f"= {money(e['m_unbal'])} \\times \\dfrac{{{_grp(e['K_col_below'])}}}"
        f"{{{_grp(e['sumK'])}}} = {money(e['M_col_below'])}\\text{{ kNm}} \\)<br/>"
        f"\\( M_{{col,above}} = M_{{unbal}}\\dfrac{{k_{{col,above}}}}{{\\Sigma K}} "
        f"= {money(e['m_unbal'])} \\times \\dfrac{{{_grp(e['K_col_above'])}}}"
        f"{{{_grp(e['sumK'])}}} = {money(e['M_col_above'])}\\text{{ kNm}} \\)")


def _cond_reason(d: dict) -> str:
    """Plain-English reason for one derived end condition."""
    if d.get("base"):
        names = {1: "fixed (moment-resisting foundation)",
                 2: "partially fixed base", 3: "pinned / nominal base"}
        return f"foundation: {names.get(d['cond'], 'base')}"
    if d["n_beams"] == 0:
        return ("no beam in this plane &rarr; nominal restraint"
                if d["cond"] == 3 else "unbraced free end (no beam)")
    depth = f"beam depth {fmt(d['max_depth'])} mm vs column {fmt(d['col_dim'])} mm"
    both = "both sides" if d["both"] else "one side only"
    deep = "&ge; column dim" if d["deep"] else "&lt; column dim"
    return f"{depth} ({deep}), {both}"


def render_end_conditions(cond_rows: List[dict], braced: bool) -> str:
    """Calc sheet: how each lift's end conditions were read off the frame."""
    if not cond_rows:
        return ""
    kind = "braced (Table 3.19)" if braced else "unbraced (Table 3.20)"
    out = ["<div class='calc-sheet'>",
           f"<h4>End Conditions from Frame Geometry &mdash; {kind}</h4>",
           "<p style='font-size:12px;color:#64748b'>Condition 1 needs beams at "
           "least as deep as the column dimension in the plane, both sides; "
           "condition 2 = shallower or one side; condition 3 = no beam (slab only); "
           "condition 4 = unbraced free end. \\( x\\text{-}x \\) uses column depth "
           "\\(h\\); \\( y\\text{-}y \\) uses width \\(b\\).</p>"]
    for r in cond_rows:
        def cell(d):
            return f"cond {d['cond']} <span style='color:#64748b'>({_cond_reason(d)})</span>"
        out.append(row(
            "Table 3.19/3.20",
            f"<h3 class='calc-section-title'>{r['name']}</h3><p>"
            f"<b>x-x:</b> top &rarr; {cell(r['top_x'])}; bottom &rarr; {cell(r['bot_x'])}<br/>"
            f"<b>y-y:</b> top &rarr; {cell(r['top_y'])}; bottom &rarr; {cell(r['bot_y'])}</p>",
            f"x: {r['top_x']['cond']}/{r['bot_x']['cond']}<br/>"
            f"y: {r['top_y']['cond']}/{r['bot_y']['cond']}"))
    out.append("</div>")
    return "".join(out)


def render_moment_trace(trace: List[dict]) -> str:
    """Steps 1-6 calc sheet: how the joint moments were distributed."""
    out = ["<div class='calc-sheet'>",
           "<h4>Column Moments by Single-Joint Distribution (BS 8110 cl 3.2.1.2.5)</h4>"]
    for e in trace:
        if "position" in e:
            out.append(row(
                "cl 3.8.4.1",
                f"<h3 class='calc-section-title'>Joint {e['joint']}</h3>"
                f"<p>Position classified as <b>{e['position']}</b> "
                f"(from which beams frame in).</p>",
                e["position"].upper()))
            continue
        out.append(row(
            "cl 3.2.1.2.5",
            f"<h3 class='calc-section-title'>Joint {e['joint']} — {e['axis']}-axis</h3>"
            f"<p>{_fem_step(e)}</p><p>{_stiffness_step(e)}</p><p>{_distribution_step(e)}</p>",
            f"\\( M_{{below}} = {money(e['M_col_below'])} \\)<br/>"
            f"\\( M_{{above}} = {money(e['M_col_above'])} \\)"))
    out.append("</div>")
    return "".join(out)


def _slenderness(g: dict, lift: cm.Lift) -> dict:
    braced = bool(g.get("braced", True))
    beta_x = bs8110.beta_effective_length(braced, lift.cond_top, lift.cond_bot)
    beta_y = bs8110.beta_effective_length(braced, lift.cond_top_y, lift.cond_bot_y)
    lex = beta_x * lift.height * 1000.0
    ley = beta_y * lift.height * 1000.0
    limit = 15 if braced else 10
    ratio = lex / lift.h
    return {"beta": beta_x, "le_h": ratio,
            "slender": ratio > limit or (ley / lift.b) > limit}


def analyze_and_design_column(payload: dict) -> dict:
    """Full Phase-2 pipeline. Returns {moment_html, designs:[...], viz:{...}}."""
    joints, lifts, g, axial_html, cond_rows = build_column_frame(payload)
    halve = bool(g.get("halve_beam_stiffness", True))
    results, trace = cm.analyze_column_stack(joints, halve_beam_stiffness=halve)

    braced = bool(g.get("braced", True))
    fcu = float(g.get("fcu", 30)); fy = float(g.get("fy", 460))
    cover = float(g.get("cover", 35)); target_dia = float(g.get("target_dia", 20))

    designs = []
    viz_lifts = []
    for idx, lift in enumerate(lifts):
        m = results.get(lift.name, {"Mx_top": 0, "Mx_bot": 0, "My_top": 0, "My_bot": 0})
        N = joints[idx].N or float(g.get("N", 1000))
        html, summary = _design_column(
            b=lift.b, h=lift.h,
            l0=lift.height, is_braced=braced,
            cond_top=lift.cond_top, cond_bot=lift.cond_bot,
            cond_top_y=lift.cond_top_y, cond_bot_y=lift.cond_bot_y, N=N,
            Mx_top=m["Mx_top"], Mx_bot=m["Mx_bot"],
            My_top=m["My_top"], My_bot=m["My_bot"],
            fcu=fcu, fy=fy, cover=cover, target_dia=target_dia)
        designs.append({"name": lift.name, "html": html})
        sl = _slenderness(g, lift)
        # Snapshot the beams framing in at this joint (for the 3D model).
        beams_viz = [{"axis": bm.axis, "side": bm.side, "span": bm.span,
                      "b": bm.b, "h": bm.h, "fem": round(bm.fem, 2)}
                     for bm in joints[idx].beams]
        viz_lifts.append({
            "id": idx, "name": lift.name, "height": lift.height, "N": N,
            "b": lift.b, "h": lift.h,
            "Mx_top": m["Mx_top"], "Mx_bot": m["Mx_bot"],
            "My_top": m["My_top"], "My_bot": m["My_bot"],
            "le_h": round(sl["le_h"], 2), "slender": sl["slender"],
            "M_des": summary["M_des"], "axis": summary["axis"],
            "bars": summary["bars"], "links": summary["links"],
            "Asc_req": summary["Asc_req"], "Asc_prov": summary["Asc_prov"],
            "utilisation": summary["utilisation"], "status": summary["status"],
            "beams": beams_viz})

    _base = lifts[0] if lifts else None
    viz = {"column": {"b": float(_base.b) if _base else 300.0,
                      "h": float(_base.h) if _base else 400.0},
           "lifts": viz_lifts}
    moment_html = (axial_html + render_end_conditions(cond_rows, braced)
                   + render_moment_trace(trace))
    return {"moment_html": moment_html, "designs": designs, "viz": viz}

