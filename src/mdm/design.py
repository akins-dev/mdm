import math
from typing import Dict, List, Tuple, Any
from .core import money, fmt, select_bar_arrangement, get_bar_area
from . import bs8110

def row(ref: str, calc: str, out: str = "") -> str:
    return f"""
    <div class="calc-row">
      <div class="calc-ref">{ref}</div>
      <div class="calc-body">{calc}</div>
      <div class="calc-out">{out}</div>
    </div>
    """

def design_section(
    name: str,
    M: float,
    V: float,
    is_support: bool = False,
    fcu: float = 30.0,
    fy: float = 460.0,
    fyv: float = 250.0,
    b: float = 230.0,
    h: float = 450.0,
    cover: float = 30.0,
    main_bar_dia: float = 20.0,
    link_dia: float = 10.0,
    span_length: float = 0.0,
    support_cond: str = "Continuous"
) -> Dict[str, Any]:
    
    html_lines = ["<div class='calc-sheet'>"]
    html_lines.append(f"<h4>Design for {name} {'(Support)' if is_support else '(Span)'}</h4>")
    
    M_abs = abs(M)
    V_abs = abs(V)
    
    html_lines.append(row(
        "Design Forces",
        f"<p>Design Moment \\( M = {money(M_abs)} \\text{{ kNm}} \\)<br/>Design Shear \\( V = {money(V_abs)} \\text{{ kN}} \\)</p>",
        f"\\( M = {money(M_abs)} \\text{{ kNm}} \\)<br/>\\( V = {money(V_abs)} \\text{{ kN}} \\)"
    ))
    
    # 1. Geometry and effective depth
    d = h - cover - link_dia - (main_bar_dia / 2.0)
    d_prime = cover + link_dia + (main_bar_dia / 2.0)
    
    html_lines.append(row(
        bs8110.REF_EFFECTIVE_DEPTH,
        f"<p>\\( d = h - c - \\phi_v - \\frac{{\\phi}}{{2}} = {fmt(h)} - {fmt(cover)} - {fmt(link_dia)} - {fmt(main_bar_dia/2)} = {money(d)} \\text{{ mm}} \\)<br/>\\( d' = c + \\phi_v + \\frac{{\\phi}}{{2}} = {fmt(cover)} + {fmt(link_dia)} + {fmt(main_bar_dia/2)} = {money(d_prime)} \\text{{ mm}} \\)</p>",
        f"\\( d = {money(d)} \\text{{ mm}} \\)<br/>\\( d' = {money(d_prime)} \\text{{ mm}} \\)"
    ))
    
    # 2. Ultimate Moment of Resistance
    Mu = bs8110.K_PRIME * fcu * b * (d ** 2) / 1e6
    html_lines.append(row(
        bs8110.REF_ULTIMATE_MOMENT,
        f"<p>\\( M_u = \\frac{{{bs8110.K_PRIME} f_{{cu}} b d^2}}{{10^6}} = \\frac{{{bs8110.K_PRIME} \\times {fmt(fcu)} \\times {fmt(b)} \\times {fmt(d)}^2}}{{10^6}} = {money(Mu)} \\text{{ kNm}} \\)</p>",
        f"\\( M_u = {money(Mu)} \\text{{ kNm}} \\)"
    ))
    
    # Check if compression reinforcement is required
    As_req = 0.0
    Asc_req = 0.0
    z = 0.0
    
    fy_eff = min(fy, 500.0)
    if fy > 500.0:
        html_lines.append(row(
            bs8110.REF_STEEL_YIELD,
            f"<p class='text-warning'><b>Note:</b> Characteristic yield strength \\( f_y \\) limited to 500 N/mm².</p>",
            f"\\( f_y = 500 \\text{{ N/mm}}^2 \\)"
        ))
    
    if M_abs <= Mu:
        K = M_abs * 1e6 / (fcu * b * (d ** 2))
        z_val = d * (0.5 + math.sqrt(abs(0.25 - K / 0.9)))
        z = min(z_val, 0.95 * d)
        
        calc_str = f"<p>\\( M \\le M_u \\), Singly Reinforced Section<br/>\\( K = \\frac{{{money(M_abs)} \\times 10^6}}{{{fmt(fcu)} \\times {fmt(b)} \\times {fmt(d)}^2}} = {money(K)} \\)<br/>\\( z = {fmt(d)} [ 0.5 + \\sqrt{{0.25 - {money(K)}/0.9}} ] = {money(z_val)} \\text{{ mm}} \\)</p>"
        
        if z_val > 0.95 * d:
            calc_str += f"<p>\\( z \\) limited to \\( 0.95d = {money(0.95 * d)} \\text{{ mm}} \\).</p>"
            
        As_req = M_abs * 1e6 / (bs8110.PARTIAL_SAFETY_STEEL * fy_eff * z)
        calc_str += f"<p>\\( A_s = \\frac{{{money(M_abs)} \\times 10^6}}{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(fy_eff)} \\times {money(z)}}} = {money(As_req)} \\text{{ mm}}^2 \\)</p>"
        
        html_lines.append(row(
            bs8110.REF_ULTIMATE_MOMENT,
            calc_str,
            f"\\( z = {money(z)} \\text{{ mm}} \\)<br/>\\( A_s = {money(As_req)} \\text{{ mm}}^2 \\)"
        ))
        
    else:
        z = d * (0.5 + math.sqrt(abs(0.25 - bs8110.K_PRIME / 0.9)))
        x = (d - z) / 0.45
        d_prime_over_x = d_prime / x
        
        calc_str = f"<p>\\( M > M_u \\), Doubly Reinforced Section<br/>\\( K' = {bs8110.K_PRIME} \\)<br/>\\( z = d [ 0.5 + \\sqrt{{0.25 - K'/0.9}} ] = {money(z)} \\text{{ mm}} \\)<br/>\\( x = \\frac{{d - z}}{{0.45}} = {money(x)} \\text{{ mm}} \\)</p>"
        
        calc_str += f"<p>\\( d'/x = {money(d_prime_over_x)} \\). "
        if d_prime_over_x <= bs8110.LIMIT_D_PRIME_X:
            calc_str += f"\\( \\le {bs8110.LIMIT_D_PRIME_X} \\), compression steel yielded.</p>"
        else:
            calc_str += f"<span class='text-danger'>\\( > {bs8110.LIMIT_D_PRIME_X} \\), compression steel has NOT yielded!</span></p>"
            
        Asc_req = (M_abs - Mu) * 1e6 / (bs8110.PARTIAL_SAFETY_STEEL * fy_eff * (d - d_prime))
        calc_str += f"<p>\\( A'_{{sc}} = \\frac{{({money(M_abs)} - {money(Mu)}) \\times 10^6}}{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(fy_eff)} \\times ({fmt(d)} - {money(d_prime)})}} = {money(Asc_req)} \\text{{ mm}}^2 \\)</p>"
        
        As_req = (Mu * 1e6 / (bs8110.PARTIAL_SAFETY_STEEL * fy_eff * z)) + Asc_req
        calc_str += f"<p>\\( A_s = \\frac{{{money(Mu)} \\times 10^6}}{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(fy_eff)} \\times {money(z)}}} + {money(Asc_req)} = {money(As_req)} \\text{{ mm}}^2 \\)</p>"
        
        html_lines.append(row(
            bs8110.REF_COMPRESSION_YIELD,
            calc_str,
            f"\\( A'_{{sc}} = {money(Asc_req)} \\text{{ mm}}^2 \\)<br/>\\( A_s = {money(As_req)} \\text{{ mm}}^2 \\)"
        ))
        
    # Minimum steel area
    As_min_pct = 0.24 if fy_eff <= 250 else 0.13
    As_min = (As_min_pct / 100.0) * b * h
    if As_req < As_min:
        html_lines.append(row(
            bs8110.REF_MIN_STEEL,
            f"<p>Minimum tension steel: \\( A_{{s,min}} = {As_min_pct}\\% b h = {money(As_min)} \\text{{ mm}}^2 \\)</p>",
            f"Use \\( A_s = {money(As_min)} \\text{{ mm}}^2 \\)"
        ))
        As_req = As_min
        
    Asc_min = 0.002 * b * h
    if Asc_req > 0 and Asc_req < Asc_min:
        html_lines.append(row(
            bs8110.REF_MIN_STEEL,
            f"<p>Minimum compression steel: \\( A'_{{sc,min}} = 0.2\\% b h = {money(Asc_min)} \\text{{ mm}}^2 \\)</p>",
            f"Use \\( A'_{{sc}} = {money(Asc_min)} \\text{{ mm}}^2 \\)"
        ))
        Asc_req = Asc_min
        
    # Maximum steel area
    As_max = 0.04 * b * h
    max_steel_str = ""
    if As_req > As_max:
        max_steel_str += f"<p class='text-danger'><b>WARNING:</b> \\( A_s = {money(As_req)} > 4\\% \\) limit ({money(As_max)} mm&sup2;).</p>"
    if Asc_req > As_max:
        max_steel_str += f"<p class='text-danger'><b>WARNING:</b> \\( A'_{{sc}} = {money(Asc_req)} > 4\\% \\) limit ({money(As_max)} mm&sup2;).</p>"
    if max_steel_str:
        html_lines.append(row(bs8110.REF_MAX_STEEL, max_steel_str, "EXCEEDS LIMIT"))
        
    # Select bar arrangement
    count, dia, area_prov = select_bar_arrangement(As_req, b, cover, link_dia, is_compression=False, target_dia=int(main_bar_dia))
    
    bar_str = f"<p>Main Tension Steel:<br/>Required: {money(As_req)} mm&sup2;</p>"
    if count > 0:
        bar_out = f"Provide {count}Y{dia}<br/>\\( (A_s = {money(area_prov)} \\text{{ mm}}^2) \\)"
    else:
        bar_str += f"<p>Cannot fit required reinforcement in a single layer. Provide \\( A_s \\ge {money(As_req)} \\text{{ mm}}^2 \\) in multiple layers.</p>"
        area_prov = As_req
        dia = main_bar_dia
        bar_out = "Multiple layers"
        
    if Asc_req > 0:
        count_c, dia_c, area_prov_c = select_bar_arrangement(Asc_req, b, cover, link_dia, is_compression=True)
        bar_str += f"<p>Compression Steel:<br/>Required: {money(Asc_req)} mm&sup2;</p>"
        if count_c > 0:
            bar_out += f"<br/><br/>Provide {count_c}Y{dia_c}<br/>\\( (A'_{{sc}} = {money(area_prov_c)} \\text{{ mm}}^2) \\)"
        else:
            bar_str += f"<p>Provide Compression Steel \\( A'_{{sc}} \\ge {money(Asc_req)} \\text{{ mm}}^2 \\).</p>"
            bar_out += "<br/><br/>Multiple layers"
            
    html_lines.append(row(bs8110.REF_BAR_SELECTION, bar_str, bar_out))
            
    # Spacing Check
    if count > 1:
        actual_spacing = (b - 2 * cover - 2 * link_dia - count * dia) / (count - 1)
        min_spacing = max(dia, 25.0)
        
        spacing_str = f"<p>Clear spacing = \\( \\frac{{{fmt(b)} - 2({fmt(cover)}) - 2({fmt(link_dia)}) - {count}({fmt(dia)})}}{{{count - 1}}} = {money(actual_spacing)} \\text{{ mm}} \\)</p>"
        if actual_spacing >= min_spacing:
            spacing_out = "Spacing OK"
        else:
            spacing_str += f"<p class='text-danger'>Warning: {money(actual_spacing)} mm &lt; minimum {money(min_spacing)} mm.</p>"
            spacing_out = "Spacing FAIL"
            
        html_lines.append(row("Spacing Check", spacing_str, spacing_out))
        
    # Shear Design
    fyv_eff = min(fyv, 460.0)
    v = V_abs * 1000 / (b * d)
    shear_str = f"<p>Design shear stress \\( v = \\frac{{{money(V_abs)} \\times 1000}}{{{fmt(b)} \\times {money(d)}}} = {money(v)} \\text{{ N/mm}}^2 \\)</p>"
    
    v_max = min(0.8 * math.sqrt(fcu), 5.0)
    if v > v_max:
        shear_str += f"<p class='text-danger'><b>WARNING:</b> \\( v \\) exceeds max allowed \\( {money(v_max)} \\text{{ N/mm}}^2 \\).</p>"
        
    html_lines.append(row(bs8110.REF_MAX_SHEAR, shear_str, f"\\( v = {money(v)} \\text{{ N/mm}}^2 \\)"))
        
    percent_As = (100 * area_prov) / (b * d)
    percent_As_eff = min(max(percent_As, 0.15), 3.0)
    fcu_for_vc = min(fcu, 40.0)
    
    f_depth = max(math.pow(400.0 / d, 0.25), 1.0)
    vc = 0.79 * math.pow(percent_As_eff, 1.0/3.0) * f_depth / 1.25 * math.pow(fcu_for_vc/25.0, 1.0/3.0)
    
    vc_str = f"<p>\\( \\frac{{100A_s}}{{bd}} = {money(percent_As)}\\% \\)<br/>"
    vc_str += f"Depth factor \\( (400/d)^{{1/4}} = {money(f_depth)} \\)<br/>"
    vc_str += f"\\( v_c = {money(vc)} \\text{{ N/mm}}^2 \\)</p>"
    
    html_lines.append(row(bs8110.REF_SHEAR_CAPACITY, vc_str, f"\\( v_c = {money(vc)} \\text{{ N/mm}}^2 \\)"))
    
    asv = 2 * get_bar_area(link_dia)
    link_str = ""
    if v < 0.5 * vc:
        link_str = f"<p>\\( v < 0.5 v_c \\) ({money(0.5*vc)}). Nominal links in practice.<br/>"
        sv_req = bs8110.PARTIAL_SAFETY_STEEL * fyv_eff * asv / (0.4 * b)
        link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} A_{{sv}} f_{{yv}}}}{{0.4 b}} = {money(sv_req)} \\text{{ mm}} \\)</p>"
    elif v <= vc + 0.4:
        link_str = f"<p>\\( v \\le v_c + 0.4 \\) ({money(vc+0.4)}). Nominal links.<br/>"
        sv_req = bs8110.PARTIAL_SAFETY_STEEL * fyv_eff * asv / (0.4 * b)
        link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} A_{{sv}} f_{{yv}}}}{{0.4 b}} = {money(sv_req)} \\text{{ mm}} \\)</p>"
    else:
        link_str = f"<p>\\( v > v_c + 0.4 \\). Design shear links required.<br/>"
        sv_req = bs8110.PARTIAL_SAFETY_STEEL * fyv_eff * asv / (b * (v - vc))
        link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} A_{{sv}} f_{{yv}}}}{{b (v - v_c)}} = {money(sv_req)} \\text{{ mm}} \\)</p>"
        
    sv_max = min(0.75 * d, 300)
    link_str += f"<p>Maximum spacing \\( S_{{v,max}} = {money(sv_max)} \\text{{ mm}} \\).</p>"
    
    sv = min(sv_req, sv_max)
    sv = math.floor(sv / 25.0) * 25.0
    
    html_lines.append(row(bs8110.REF_SHEAR_LINKS, link_str, f"Provide Y{int(link_dia)} @ {int(sv)} c/c"))
    
    # Deflection Check
    if not is_support and span_length > 0:
        if support_cond.lower() == "cantilever":
            basic_span_d = 7
        elif support_cond.lower() == "simply supported":
            basic_span_d = 20
        else:
            basic_span_d = 26
            
        fs = (2.0 / 3.0) * fy * (As_req / area_prov)
        M_bd2 = (M_abs * 1e6) / (b * d * d)
        mf_calc = 0.55 + (477.0 - fs) / (120.0 * (0.9 + M_bd2))
        mf = min(mf_calc, 2.0)
        
        allowable_span_d = basic_span_d * mf
        actual_span_d = span_length / d
        
        defl_str = f"<p>Basic span/d for {support_cond} = {basic_span_d}<br/>"
        defl_str += f"\\( f_s = \\frac{{2 f_y A_{{s,req}}}}{{3 A_{{s,prov}}}} = {money(fs)} \\text{{ N/mm}}^2 \\)<br/>"
        defl_str += f"\\( \\frac{{M}}{{bd^2}} = {money(M_bd2)} \\text{{ N/mm}}^2 \\)<br/>"
        defl_str += f"Mod. Factor = \\( 0.55 + \\frac{{477 - {money(fs)}}}{{120(0.9 + {money(M_bd2)})}} = {money(mf_calc)} \\le 2.0 \\) (Use {money(mf)})<br/>"
        defl_str += f"Allowable span/d = \\( {basic_span_d} \\times {money(mf)} = {money(allowable_span_d)} \\)<br/>"
        defl_str += f"Actual span/d = {money(actual_span_d)}</p>"
        
        if actual_span_d <= allowable_span_d:
            defl_out = "Deflection OK"
        else:
            defl_str += f"<p class='text-danger'>Warning: {money(actual_span_d)} &gt; {money(allowable_span_d)}</p>"
            defl_out = "Deflection FAIL"
            
        html_lines.append(row(bs8110.REF_DEFLECTION_BASIC, defl_str, defl_out))

    html_lines.append("</div>")
    
    return {
        "html": "".join(html_lines)
    }
