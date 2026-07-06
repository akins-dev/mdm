import math
from typing import Dict, List, Tuple, Any
from ..models.beam import money, fmt
from . import bs8110

def row(ref: str, calc: str, out: str = "", status: str = "success") -> str:
    out_html = f"<span class='text-{status}'>{out}</span>" if out else ""
    return f"""
    <div class="calc-row">
      <div class="calc-ref">{ref}</div>
      <div class="calc-body">{calc}</div>
      <div class="calc-out">{out_html}</div>
    </div>
    """

def draw_section_svg(b, h, cover, link_dia, layer_counts, dia, layer_counts_c, dia_c, is_support):
    scale = min(200.0 / b, 250.0 / h)
    dw = b * scale
    dh = h * scale
    dcover = cover * scale
    dlink = link_dia * scale
    
    svg_w = dw + 100
    svg_h = dh + 80
    ox = 20
    oy = 20
    
    lines = []
    lines.append(f"<svg viewBox='0 0 {svg_w} {svg_h}' width='100%' style='max-width: {svg_w}px;'>")
    lines.append("<defs><marker id='arrow' markerWidth='10' markerHeight='10' refX='5' refY='5' orient='auto-start-reverse'><path d='M 0 2 L 5 5 L 0 8 z' fill='#6b7280'/></marker></defs>")
    lines.append(f"<rect x='{ox}' y='{oy}' width='{dw}' height='{dh}' fill='#e5e7eb' stroke='#374151' stroke-width='2'/>")
    
    link_x = ox + dcover
    link_y = oy + dcover
    link_w = dw - 2 * dcover
    link_h = dh - 2 * dcover
    lines.append(f"<rect x='{link_x}' y='{link_y}' width='{link_w}' height='{link_h}' fill='none' stroke='#1f2937' stroke-width='{max(2.0, dlink)}' rx='4'/>")
    
    if is_support:
        top_counts, top_dia, bot_counts, bot_dia = layer_counts, dia, layer_counts_c, dia_c
    else:
        top_counts, top_dia, bot_counts, bot_dia = layer_counts_c, dia_c, layer_counts, dia
        
    def draw_bars(n, bar_dia, y_center):
        if n <= 0: return ""
        r = (bar_dia / 2.0) * scale
        inner_w = dw - 2*dcover - 2*dlink - 2*r
        spacing = inner_w / max(1, n - 1) if n > 1 else 0
        start_x = ox + dcover + dlink + r
        if n == 1: start_x = ox + dw / 2.0
        
        circs = []
        for i in range(n):
            cx = start_x + i * spacing
            circs.append(f"<circle cx='{cx}' cy='{y_center}' r='{max(3.0, r)}' fill='#111827'/>")
        return "".join(circs)

    if top_counts:
        top_spacer = max(25.0, top_dia) * scale
        ty = oy + dcover + dlink + (top_dia / 2.0) * scale
        total_top = 0
        for n in top_counts:
            lines.append(draw_bars(n, top_dia, ty))
            ty += top_spacer + top_dia * scale
            total_top += n
        lines.append(f"<text x='{ox + dw + 10}' y='{oy + dcover + 15}' fill='#1f2937' font-size='12' text-anchor='start'>{total_top}Y{int(top_dia)}</text>")
        
    if bot_counts:
        bot_spacer = max(25.0, bot_dia) * scale
        by = oy + dh - dcover - dlink - (bot_dia / 2.0) * scale
        total_bot = 0
        for n in bot_counts:
            lines.append(draw_bars(n, bot_dia, by))
            by -= bot_spacer + bot_dia * scale
            total_bot += n
        lines.append(f"<text x='{ox + dw + 10}' y='{oy + dh - dcover - 5}' fill='#1f2937' font-size='12' text-anchor='start'>{total_bot}Y{int(bot_dia)}</text>")
        
    dim_y = oy + dh + 30
    lines.append(f"<line x1='{ox}' y1='{dim_y-5}' x2='{ox}' y2='{dim_y+5}' stroke='#6b7280'/>")
    lines.append(f"<line x1='{ox+dw}' y1='{dim_y-5}' x2='{ox+dw}' y2='{dim_y+5}' stroke='#6b7280'/>")
    lines.append(f"<line x1='{ox}' y1='{dim_y}' x2='{ox+dw}' y2='{dim_y}' stroke='#6b7280' marker-start='url(#arrow)' marker-end='url(#arrow)'/>")
    lines.append(f"<text x='{ox+dw/2}' y='{dim_y-5}' fill='#4b5563' font-size='12' text-anchor='middle'>{int(b)}</text>")
    
    dim_x = ox + dw + 45
    lines.append(f"<line x1='{dim_x-5}' y1='{oy}' x2='{dim_x+5}' y2='{oy}' stroke='#6b7280'/>")
    lines.append(f"<line x1='{dim_x-5}' y1='{oy+dh}' x2='{dim_x+5}' y2='{oy+dh}' stroke='#6b7280'/>")
    lines.append(f"<line x1='{dim_x}' y1='{oy}' x2='{dim_x}' y2='{oy+dh}' stroke='#6b7280' marker-start='url(#arrow)' marker-end='url(#arrow)'/>")
    lines.append(f"<text x='{dim_x+10}' y='{oy+dh/2+4}' fill='#4b5563' font-size='12' text-anchor='start'>{int(h)}</text>")
    
    lines.append("</svg>")
    return "".join(lines)

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
    support_cond: str = "Continuous",
    highlight_title: str = "",
    bg_color: str = "",
    show_position: bool = True,
    notes: list = None,
    skip_shear: bool = False,
    skip_drawing: bool = False
) -> Dict[str, Any]:
    
    style_attr = f" style='background-color: {bg_color}; border-color: #f59e0b; border-width: 2px;'" if bg_color else ""
    html_lines = [f"<div class='calc-sheet'{style_attr}>"]
    
    suffix = f" {'(Support)' if is_support else '(Span)'}" if show_position else ""
    header_text = f"Design for {name}{suffix}"
    if highlight_title:
        header_text += f" - <span style='background-color: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; font-weight: bold;'>{highlight_title}</span>"
        
    html_lines.append(f"<h4>{header_text}</h4>")
    html_lines.append("<p class='text-sm text-gray-600 mb-2'><b>Note:</b> Section designed strictly as a Rectangular Beam (per Oyenuga). Partial safety factor for steel \\(\\gamma_m = 1.05\\), hence using \\(0.95 f_y\\) instead of \\(0.87 f_y\\).</p>")
    
    if notes:
        html_lines.append("<div class='mb-4 p-3' style='background-color: #000; color: #fff; border-radius: 4px; font-size: 0.9em;'>")
        html_lines.append("<div style='font-weight: bold; margin-bottom: 8px;'>When designing reinforcement:</div>")
        html_lines.append("<ul style='list-style-type: disc; padding-left: 20px; margin-bottom: 8px;'>")
        for note in notes[:-1]:
            html_lines.append(f"<li>{note}</li>")
        html_lines.append("</ul>")
        html_lines.append(f"<p style='margin: 0;'>{notes[-1]}</p>")
        html_lines.append("</div>")
    
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
        f"<div style='font-weight: bold; text-decoration: underline; margin-bottom: 8px; font-size: 0.95em; color: #374151;'>Section Properties</div><p>\\( d = h - c - \\phi_v - \\frac{{\\phi}}{{2}} = {fmt(h)} - {fmt(cover)} - {fmt(link_dia)} - {fmt(main_bar_dia/2)} = {money(d)} \\text{{ mm}} \\)<br/>\\( d' = c + \\phi_v + \\frac{{\\phi}}{{2}} = {fmt(cover)} + {fmt(link_dia)} + {fmt(main_bar_dia/2)} = {money(d_prime)} \\text{{ mm}} \\)</p>",
        f"\\( d = {money(d)} \\text{{ mm}} \\)<br/>\\( d' = {money(d_prime)} \\text{{ mm}} \\)"
    ))
    
    # 2. Ultimate Moment of Resistance
    Mu = bs8110.K_PRIME * fcu * b * (d ** 2) / 1e6
    comp_msg = "<b>Compression reinforcement<br/>not required</b>" if M_abs <= Mu else "<b>Compression reinforcement<br/>required</b>"
    reinforcement_type_str = "<b>Singly Reinforced</b> \\( (M \\le M_u) \\)" if M_abs <= Mu else "<b>Doubly Reinforced</b> \\( (M > M_u) \\)"
    html_lines.append(row(
        bs8110.REF_ULTIMATE_MOMENT,
        f"<div style='font-weight: bold; text-decoration: underline; margin-bottom: 8px; font-size: 0.95em; color: #374151;'>Flexural Design</div><p>\\( M_u = \\frac{{{bs8110.K_PRIME} f_{{cu}} b d^2}}{{10^6}} = \\frac{{{bs8110.K_PRIME} \\times {fmt(fcu)} \\times {fmt(b)} \\times {fmt(d)}^2}}{{10^6}} = {money(Mu)} \\text{{ kNm}} \\)</p><p>{reinforcement_type_str}</p>",
        f"\\( M_u = {money(Mu)} \\text{{ kNm}} \\)<br/><br/>{comp_msg}"
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
        
        calc_str = f"<div style='font-weight: bold; text-decoration: underline; margin-bottom: 8px; font-size: 0.95em; color: #374151;'>Neutral Axis check</div><p>\\( K = \\frac{{M}}{{f_{{cu}} b d^2}} = \\frac{{{money(M_abs)} \\times 10^6}}{{{fmt(fcu)} \\times {fmt(b)} \\times {fmt(d)}^2}} = {money(K)} \\)<br/>"
        calc_str += f"\\( z = d \\left[ 0.5 + \\sqrt{{0.25 - \\frac{{K}}{{0.9}}}} \\right] = {money(z_val)} \\text{{ mm}} \\)<br/>"
        calc_str += f"\\( z \\le 0.95d \\Rightarrow z \\le {money(0.95 * d)} \\text{{ mm}} \\)<br/>"
        
        if z_val > 0.95 * d:
            calc_str += f"Since \\( z > 0.95d \\), adopt \\( z = {money(0.95 * d)} \\text{{ mm}} \\)</p>"
        else:
            calc_str += f"Since \\( z \\le 0.95d \\), adopt \\( z = {money(z_val)} \\text{{ mm}} \\)</p>"
            
        As_req = M_abs * 1e6 / (bs8110.PARTIAL_SAFETY_STEEL * fy_eff * z)
        calc_str += f"<p>\\( A_s = \\frac{{M}}{{{bs8110.PARTIAL_SAFETY_STEEL} f_y z}} = \\frac{{{money(M_abs)} \\times 10^6}}{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(fy_eff)} \\times {money(z)}}} = {money(As_req)} \\text{{ mm}}^2 \\)</p>"
        
        html_lines.append(row(
            bs8110.REF_ULTIMATE_MOMENT,
            calc_str,
            f"\\( z = {money(z)} \\text{{ mm}} \\)<br/>\\( A_s = {money(As_req)} \\text{{ mm}}^2 \\)"
        ))
        
    else:
        z = d * (0.5 + math.sqrt(abs(0.25 - bs8110.K_PRIME / 0.9)))
        x = (d - z) / 0.45
        d_prime_over_x = d_prime / x
        
        calc_str = f"<div style='font-weight: bold; text-decoration: underline; margin-bottom: 8px; font-size: 0.95em; color: #374151;'>Neutral Axis check</div><p>\\( K' = {bs8110.K_PRIME} \\)<br/>\\( z = d \\left[ 0.5 + \\sqrt{{0.25 - \\frac{{K'}}{{0.9}}}} \\right] = {money(z)} \\text{{ mm}} \\)<br/>\\( x = \\frac{{d - z}}{{0.45}} = {money(x)} \\text{{ mm}} \\)</p>"
        
        calc_str += f"<p>\\( d'/x = {money(d_prime_over_x)} \\). "
        if d_prime_over_x <= bs8110.LIMIT_D_PRIME_X:
            calc_str += f"\\( \\le {bs8110.LIMIT_D_PRIME_X} \\) (yields).</p>"
        else:
            calc_str += f"<span class='text-danger'>\\( > {bs8110.LIMIT_D_PRIME_X} \\) (no yield)</span></p>"
            
        Asc_req = (M_abs - Mu) * 1e6 / (bs8110.PARTIAL_SAFETY_STEEL * fy_eff * (d - d_prime))
        calc_str += f"<p>\\( A'_{{sc}} = \\frac{{(M - M_u) \\times 10^6}}{{{bs8110.PARTIAL_SAFETY_STEEL} f_y (d - d')}} = \\frac{{({money(M_abs)} - {money(Mu)}) \\times 10^6}}{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(fy_eff)} \\times ({fmt(d)} - {money(d_prime)})}} = {money(Asc_req)} \\text{{ mm}}^2 \\)</p>"
        
        As_req = (Mu * 1e6 / (bs8110.PARTIAL_SAFETY_STEEL * fy_eff * z)) + Asc_req
        calc_str += f"<p>\\( A_s = \\frac{{M_u \\times 10^6}}{{{bs8110.PARTIAL_SAFETY_STEEL} f_y z}} + A'_{{sc}} = \\frac{{{money(Mu)} \\times 10^6}}{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(fy_eff)} \\times {money(z)}}} + {money(Asc_req)} = {money(As_req)} \\text{{ mm}}^2 \\)</p>"
        
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
            f"<p>\\( A_{{s,min}} = {As_min_pct}\\% b h = {money(As_min)} \\text{{ mm}}^2 \\)</p>",
            f"Use \\( A_s = {money(As_min)} \\text{{ mm}}^2 \\)"
        ))
        As_req = As_min
        
    Asc_min = 0.002 * b * h
    if Asc_req > 0 and Asc_req < Asc_min:
        html_lines.append(row(
            bs8110.REF_MIN_STEEL,
            f"<p>\\( A'_{{sc,min}} = 0.2\\% b h = {money(Asc_min)} \\text{{ mm}}^2 \\)</p>",
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
        html_lines.append(row(bs8110.REF_MAX_STEEL, max_steel_str, "EXCEEDS LIMIT", "danger"))
        
    # Select bar arrangement
    layer_counts, dia, area_prov = bs8110.select_bar_arrangement(As_req, b, cover, link_dia, is_compression=False, target_dia=int(main_bar_dia))
    
    tension_loc = ""
    compression_loc = ""
    if show_position:
        tension_loc = " (Top)" if is_support else " (Bottom)"
        compression_loc = " (Bottom)" if is_support else " (Top)"
    
    bar_str = f"<p><b>Tension Steel:</b> \\( A_{{s,req}} = {money(As_req)} \\text{{ mm}}^2 \\)</p>"
    if layer_counts:
        count = sum(layer_counts)
        layers_str = f" in {len(layer_counts)} layers" if len(layer_counts) > 1 else ""
        bar_out = f"Provide {count}Y{dia}{layers_str}{tension_loc}<br/>\\( (A_s = {money(area_prov)} \\text{{ mm}}^2) \\)"
    else:
        bar_str += f"<p>Cannot fit required reinforcement in 2 layers. Provide \\( A_s \\ge {money(As_req)} \\text{{ mm}}^2 \\) in multiple layers.</p>"
        area_prov = As_req
        dia = main_bar_dia
        layer_counts = []
        bar_out = f"Multiple layers{tension_loc}"
        
    layer_counts_c = []
    dia_c = main_bar_dia
    
    if Asc_req > 0:
        layer_counts_c, dia_c, area_prov_c = bs8110.select_bar_arrangement(Asc_req, b, cover, link_dia, is_compression=True)
        bar_str += f"<p><b>Compression Steel:</b> \\( A'_{{sc,req}} = {money(Asc_req)} \\text{{ mm}}^2 \\)</p>"
        if layer_counts_c:
            count_c = sum(layer_counts_c)
            layers_c_str = f" in {len(layer_counts_c)} layers" if len(layer_counts_c) > 1 else ""
            bar_out += f"<br/><br/>Provide {count_c}Y{dia_c}{layers_c_str}{compression_loc}<br/>\\( (A'_{{sc}} = {money(area_prov_c)} \\text{{ mm}}^2) \\)"
        else:
            bar_str += f"<p>Provide Compression Steel \\( A'_{{sc}} \\ge {money(Asc_req)} \\text{{ mm}}^2 \\).</p>"
            bar_out += f"<br/><br/>Multiple layers{compression_loc}"
            
    html_lines.append(row("", bar_str, bar_out))
            
    # Spacing Check
    outer_count = layer_counts[0] if layer_counts else 1
    if outer_count > 1:
        min_spacing = max(dia, 25.0)
        b_req = 2 * cover + 2 * link_dia + outer_count * dia + (outer_count - 1) * min_spacing
        
        min_spacing_calc_str = f"<div style='font-weight: bold; text-decoration: underline; margin-bottom: 8px; font-size: 0.95em; color: #374151;'>Spacing Check</div>"
        min_spacing_calc_str += f"spacing = bar diameter (\\( \\phi \\)) or \\( h_{{agg}} + 5 \\), whichever is greater.<br/>"
        min_spacing_calc_str += f"spacing = {fmt(dia)} or {20 + 5} = {fmt(min_spacing)} mm<br/>"
        
        spacing_str = f"<p>{min_spacing_calc_str}"
        spacing_str += f"\\( b_{{req}} = 2c + 2\\phi_v + n\\phi + (n-1) \\times \\text{{spacing}} \\)<br/>"
        spacing_str += f"\\( b_{{req}} = 2({fmt(cover)}) + 2({fmt(link_dia)}) + {outer_count}({fmt(dia)}) + {outer_count - 1}({fmt(min_spacing)}) = {fmt(b_req)} \\text{{ mm}} \\)</p>"
        
        if b_req <= b:
            spacing_out = f"\\( (b_{{req}} \\le b) \\)<br/>Spacing OK"
            spacing_status = "success"
        else:
            spacing_str += f"<p class='text-danger'><b>WARNING:</b> Required width ({money(b_req)} mm) &gt; Beam width ({fmt(b)} mm).</p>"
            spacing_out = "EXCEEDS LIMIT"
            spacing_status = "danger"
            
        html_lines.append(row(bs8110.REF_MAX_SPACING, spacing_str, spacing_out, spacing_status))
        
    # Deflection Check
    if (not is_support or not show_position) and span_length > 0:
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
        
        defl_str = f"<div style='font-weight: bold; text-decoration: underline; margin-bottom: 8px; font-size: 0.95em; color: #374151;'>Deflection Check ({support_cond})</div><p>"
        defl_str += f"\\( f_s = \\frac{{2 f_y A_{{s,req}}}}{{3 A_{{s,prov}}}} = {money(fs)} \\text{{ N/mm}}^2 \\)<br/>"
        defl_str += f"\\( \\frac{{M}}{{bd^2}} = {money(M_bd2)} \\text{{ N/mm}}^2 \\)<br/>"
        defl_str += f"M.F. = \\( 0.55 + \\frac{{477 - {money(fs)}}}{{120(0.9 + {money(M_bd2)})}} = {money(mf_calc)} \\le 2.0 \\) (Use {money(mf)})<br/>"
        defl_str += f"Basic span ratio = {basic_span_d}<br/>"
        defl_str += f"Allowable span/d = \\( {basic_span_d} \\times {money(mf)} = {money(allowable_span_d)} \\)<br/>"
        if not show_position:
            defl_str += f"Actual span/d (using max span length) = \\( \\frac{{{money(span_length)}}}{{{fmt(d)}}} = {money(actual_span_d)} \\)</p>"
        else:
            defl_str += f"Actual span/d = \\( \\frac{{{money(span_length)}}}{{{fmt(d)}}} = {money(actual_span_d)} \\)</p>"
        
        if actual_span_d <= allowable_span_d:
            defl_out = f"Deflection OK<br/>\\( (\\text{{Actual}} \\le \\text{{Allowable}}) \\)"
            defl_status = "success"
        else:
            defl_str += f"<p class='text-danger'><b>WARNING:</b> Actual ratio ({money(actual_span_d)}) &gt; Allowable ({money(allowable_span_d)}).<br/><b>Advise:</b> Increase beam height (h).</p>"
            defl_out = "EXCEEDS LIMIT"
            defl_status = "danger"
            
        html_lines.append(row(bs8110.REF_DEFLECTION_BASIC, defl_str, defl_out, defl_status))
        
    if not skip_shear:
        # Shear Design
        fyv_eff = min(fyv, 460.0)
        v = V_abs * 1000 / (b * d)
        shear_str = f"<div style='font-weight: bold; text-decoration: underline; margin-bottom: 8px; font-size: 0.95em; color: #374151;'>Shear Design</div><p>\\( v = \\frac{{V \\times 1000}}{{b d}} = \\frac{{{money(V_abs)} \\times 1000}}{{{fmt(b)} \\times {fmt(d)}}} = {money(v)} \\text{{ N/mm}}^2 \\)</p>"
        
        v_max_calc = 0.8 * math.sqrt(fcu)
        v_max = min(v_max_calc, 5.0)
        shear_str += f"<p>\\( v_{{max}} = 0.8\\sqrt{{f_{{cu}}}} \\) or 5, whichever is lesser.<br/>"
        shear_str += f"\\( v_{{max}} = 0.8\\sqrt{{{fmt(fcu)}}} \\) or 5 = \\( {money(v_max)} \\text{{ N/mm}}^2 \\)</p>"
        
        if v > v_max:
            shear_str += f"<p class='text-danger'><b>WARNING:</b> \\( v = {money(v)} > v_{{max}} = {money(v_max)} \\text{{ N/mm}}^2 \\). Section Inadequate.<br/><b>Advise:</b> Increase beam width (b), beam height (h), or both.</p>"
            shear_out = "SECTION INADEQUATE"
            shear_status = "danger"
        else:
            shear_out = f"\\( (v \\le v_{{max}}) \\)<br/>Section OK"
            shear_status = "success"
            
        html_lines.append(row(bs8110.REF_MAX_SHEAR, shear_str, shear_out, shear_status))
            
        percent_As = (100 * area_prov) / (b * d)
        percent_As_eff = min(max(percent_As, 0.15), 3.0)
        fcu_for_vc = min(fcu, 40.0)
        
        f_depth = max(math.pow(400.0 / d, 0.25), 1.0)
        vc = 0.79 * math.pow(percent_As_eff, 1.0/3.0) * f_depth / 1.25 * math.pow(fcu_for_vc/25.0, 1.0/3.0)
        
        vc_str = f"<p>\\( \\frac{{100A_s}}{{bd}} = {money(percent_As)}\\% \\)<br/>"
        vc_str += f"Depth factor \\( (400/d)^{{1/4}} = {money(f_depth)} \\)<br/>"
        vc_str += f"\\( v_c = {money(vc)} \\text{{ N/mm}}^2 \\)</p>"
        
        html_lines.append(row(bs8110.REF_SHEAR_CAPACITY, vc_str, f"\\( v_c = {money(vc)} \\text{{ N/mm}}^2 \\)"))
        
        if v < 0.5 * vc:
            req_str = f"<b>Condition satisfied:</b> \\( v < 0.5v_c \\)<br/>\\( {money(v)} < {money(0.5*vc)} \\)"
            req_out = "Shear reinforcement<br/>not required"
        elif v <= vc + 0.4:
            req_str = f"<b>Condition satisfied:</b> \\( 0.5v_c < v \\le (v_c + 0.4) \\)<br/>\\( {money(0.5*vc)} < {money(v)} \\le {money(vc+0.4)} \\)"
            req_out = "Shear reinforcement<br/>required"
        else:
            req_str = f"<b>Condition satisfied:</b> \\( (v_c + 0.4) < v \\)<br/>\\( {money(vc+0.4)} < {money(v)} \\)"
            req_out = "Shear reinforcement<br/>required"
            
        html_lines.append(row("Table 3.7", req_str, req_out, "success"))
        
        asv_single = bs8110.get_bar_area(link_dia)
        asv = 2 * asv_single
        
        asv_str = f"\\( A_{{sv}} \\) (2-legged stirrup) = \\( 2 \\times \\text{{Area of }}\\phi_v \\)<br/>"
        asv_str += f"\\( A_{{sv}} = 2 \\times {fmt(asv_single)} = {fmt(asv)} \\text{{ mm}}^2 \\)<br/>"
        
        link_str = ""
        link_out = ""
        
        if v < 0.5 * vc:
            link_str += f"<p>Shear reinforcement is not required.</p>"
            link_out = "None Required"
        elif v <= vc + 0.4:
            link_str += f"<p>\\( A_{{sv}} \\ge \\frac{{0.4b S_v}}{{0.95 f_{{yv}}}} \\implies \\)<br/>"
            link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} A_{{sv}} f_{{yv}}}}{{0.4b}} \\)<br/>"
            link_str += asv_str
            sv_req = bs8110.PARTIAL_SAFETY_STEEL * fyv_eff * asv / (0.4 * b)
            link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(asv)} \\times {fmt(fyv_eff)}}}{{0.4 \\times {fmt(b)}}} = {money(sv_req)} \\text{{ mm}} \\)</p>"
        else:
            link_str += f"<p>\\( A_{{sv}} \\ge \\frac{{b S_v (v - v_c)}}{{0.95 f_{{yv}}}} \\implies \\)<br/>"
            link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} A_{{sv}} f_{{yv}}}}{{b(v - v_c)}} \\)<br/>"
            link_str += asv_str
            sv_req = bs8110.PARTIAL_SAFETY_STEEL * fyv_eff * asv / (b * (v - vc))
            link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(asv)} \\times {fmt(fyv_eff)}}}{{{fmt(b)}({money(v)} - {money(vc)})}} = {money(sv_req)} \\text{{ mm}} \\)</p>"
            
        if v >= 0.5 * vc:
            if Asc_req > 0:
                sv_max = min(0.75 * d, 300, 12 * dia_c)
                link_str += f"<p>For doubly reinforced:<br/>\\( S_{{v,max}} = 0.75d \\text{{, }} 300 \\text{{, or }} 12\\phi_c \\text{{ (whichever is lesser)}} \\)<br/>"
                link_str += f"\\( S_{{v,max}} = 0.75({fmt(d)}) \\text{{, }} 300 \\text{{, or }} 12({fmt(dia_c)}) = {fmt(sv_max)} \\text{{ mm}} \\)</p>"
            else:
                sv_max = min(0.75 * d, 300)
                link_str += f"<p>For singly reinforced:<br/>\\( S_{{v,max}} = 0.75d \\text{{ or }} 300 \\text{{ (whichever is lesser)}} \\)<br/>"
                link_str += f"\\( S_{{v,max}} = 0.75({fmt(d)}) \\text{{ or }} 300 = {fmt(sv_max)} \\text{{ mm}} \\)</p>"
            
            sv = min(sv_req, sv_max)
            sv = math.floor(sv / 25.0) * 25.0
            link_out = f"Provide 2-legs Y{int(link_dia)}mm bars @ {int(sv)}mm c/c"
            
        html_lines.append(row(bs8110.REF_SHEAR_LINKS, link_str, link_out))

    if not skip_drawing:
        html_lines.append("<div class='section-drawing mt-4 border-t border-gray-200 pt-4 flex flex-col items-center'>")
        html_lines.append("<h5 class='text-md font-bold mb-2'>Beam section detailing</h5>")
        
        if not show_position:
            html_lines.append("<div style='display: flex; flex-wrap: wrap; justify-content: center; gap: 2rem;'>")
            html_lines.append("<div style='display: flex; flex-direction: column; align-items: center;'>")
            html_lines.append("<h6 class='text-sm font-semibold mb-1'>Span Detailing (Tension Bottom)</h6>")
            html_lines.append(draw_section_svg(b, h, cover, link_dia, layer_counts, dia, layer_counts_c, dia_c, False))
            html_lines.append("</div>")
            html_lines.append("<div style='display: flex; flex-direction: column; align-items: center;'>")
            html_lines.append("<h6 class='text-sm font-semibold mb-1'>Support Detailing (Tension Top)</h6>")
            html_lines.append(draw_section_svg(b, h, cover, link_dia, layer_counts, dia, layer_counts_c, dia_c, True))
            html_lines.append("</div>")
            html_lines.append("</div>")
        else:
            html_lines.append(draw_section_svg(b, h, cover, link_dia, layer_counts, dia, layer_counts_c, dia_c, is_support))
            
        html_lines.append("</div>")

    html_lines.append("</div>")
    
    return {
        "html": "".join(html_lines),
        "area_prov": area_prov,
        "Asc_req": Asc_req if 'Asc_req' in locals() else 0,
        "layer_counts": layer_counts,
        "dia": dia,
        "layer_counts_c": layer_counts_c,
        "dia_c": dia_c,
        "d": d
    }

def shear_and_drawing_section(
    name: str,
    V: float,
    b: float,
    h: float,
    d: float,
    cover: float,
    fcu: float,
    fyv: float,
    area_prov: float,
    Asc_req: float,
    link_dia: float,
    top_layer_counts: list,
    top_dia: float,
    top_layer_counts_c: list,
    top_dia_c: float,
    bot_layer_counts: list,
    bot_dia: float,
    bot_layer_counts_c: list,
    bot_dia_c: float,
    highlight_title: str = "",
    bg_color: str = ""
) -> str:
    style_attr = f" style='background-color: {bg_color}; border-color: #f59e0b; border-width: 2px;'" if bg_color else ""
    html_lines = [f"<div class='calc-sheet'{style_attr}>"]
    
    header_text = f"Design for {name}"
    if highlight_title:
        header_text += f" - <span style='background-color: #f59e0b; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; font-weight: bold;'>{highlight_title}</span>"
        
    html_lines.append(f"<h4>{header_text}</h4>")
    
    V_abs = abs(V)
    
    # Shear Design
    fyv_eff = min(fyv, 460.0)
    v = V_abs * 1000 / (b * d)
    shear_str = f"<div style='font-weight: bold; text-decoration: underline; margin-bottom: 8px; font-size: 0.95em; color: #374151;'>Shear Design</div><p>\\( v = \\frac{{V \\times 1000}}{{b d}} = \\frac{{{money(V_abs)} \\times 1000}}{{{fmt(b)} \\times {fmt(d)}}} = {money(v)} \\text{{ N/mm}}^2 \\)</p>"
    
    v_max_calc = 0.8 * math.sqrt(fcu)
    v_max = min(v_max_calc, 5.0)
    shear_str += f"<p>\\( v_{{max}} = 0.8\\sqrt{{f_{{cu}}}} \\) or 5, whichever is lesser.<br/>"
    shear_str += f"\\( v_{{max}} = 0.8\\sqrt{{{fmt(fcu)}}} \\) or 5 = \\( {money(v_max)} \\text{{ N/mm}}^2 \\)</p>"
    
    if v > v_max:
        shear_str += f"<p class='text-danger'><b>WARNING:</b> \\( v = {money(v)} > v_{{max}} = {money(v_max)} \\text{{ N/mm}}^2 \\). Section Inadequate.<br/><b>Advise:</b> Increase beam width (b), beam height (h), or both.</p>"
        shear_out = "SECTION INADEQUATE"
        shear_status = "danger"
    else:
        shear_out = f"\\( (v \\le v_{{max}}) \\)<br/>Section OK"
        shear_status = "success"
        
    html_lines.append(row(bs8110.REF_MAX_SHEAR, shear_str, shear_out, shear_status))
        
    percent_As = (100 * area_prov) / (b * d)
    percent_As_eff = min(max(percent_As, 0.15), 3.0)
    fcu_for_vc = min(fcu, 40.0)
    
    f_depth = max(math.pow(400.0 / d, 0.25), 1.0)
    vc = 0.79 * math.pow(percent_As_eff, 1.0/3.0) * f_depth / 1.25 * math.pow(fcu_for_vc/25.0, 1.0/3.0)
    
    vc_str = f"<p>\\( \\frac{{100A_s}}{{bd}} = {money(percent_As)}\\% \\)<br/>"
    vc_str += f"Depth factor \\( (400/d)^{{1/4}} = {money(f_depth)} \\)<br/>"
    vc_str += f"\\( v_c = {money(vc)} \\text{{ N/mm}}^2 \\)</p>"
    
    html_lines.append(row(bs8110.REF_SHEAR_CAPACITY, vc_str, f"\\( v_c = {money(vc)} \\text{{ N/mm}}^2 \\)"))
    
    if v < 0.5 * vc:
        req_str = f"<b>Condition satisfied:</b> \\( v < 0.5v_c \\)<br/>\\( {money(v)} < {money(0.5*vc)} \\)"
        req_out = "Shear reinforcement<br/>not required"
    elif v <= vc + 0.4:
        req_str = f"<b>Condition satisfied:</b> \\( 0.5v_c < v \\le (v_c + 0.4) \\)<br/>\\( {money(0.5*vc)} < {money(v)} \\le {money(vc+0.4)} \\)"
        req_out = "Shear reinforcement<br/>required"
    else:
        req_str = f"<b>Condition satisfied:</b> \\( (v_c + 0.4) < v \\)<br/>\\( {money(vc+0.4)} < {money(v)} \\)"
        req_out = "Shear reinforcement<br/>required"
        
    html_lines.append(row("Table 3.7", req_str, req_out, "success"))
    
    asv_single = bs8110.get_bar_area(link_dia)
    asv = 2 * asv_single
    
    asv_str = f"\\( A_{{sv}} \\) (2-legged stirrup) = \\( 2 \\times \\text{{Area of }}\\phi_v \\)<br/>"
    asv_str += f"\\( A_{{sv}} = 2 \\times {fmt(asv_single)} = {fmt(asv)} \\text{{ mm}}^2 \\)<br/>"
    
    link_str = ""
    link_out = ""
    
    if v < 0.5 * vc:
        link_str += f"<p>Shear reinforcement is not required.</p>"
        link_out = "None Required"
    elif v <= vc + 0.4:
        link_str += f"<p>\\( A_{{sv}} \\ge \\frac{{0.4b S_v}}{{0.95 f_{{yv}}}} \\implies \\)<br/>"
        link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} A_{{sv}} f_{{yv}}}}{{0.4b}} \\)<br/>"
        link_str += asv_str
        sv_req = bs8110.PARTIAL_SAFETY_STEEL * fyv_eff * asv / (0.4 * b)
        link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(asv)} \\times {fmt(fyv_eff)}}}{{0.4 \\times {fmt(b)}}} = {money(sv_req)} \\text{{ mm}} \\)</p>"
    else:
        link_str += f"<p>\\( A_{{sv}} \\ge \\frac{{b S_v (v - v_c)}}{{0.95 f_{{yv}}}} \\implies \\)<br/>"
        link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} A_{{sv}} f_{{yv}}}}{{b(v - v_c)}} \\)<br/>"
        link_str += asv_str
        sv_req = bs8110.PARTIAL_SAFETY_STEEL * fyv_eff * asv / (b * (v - vc))
        link_str += f"\\( S_v = \\frac{{{bs8110.PARTIAL_SAFETY_STEEL} \\times {fmt(asv)} \\times {fmt(fyv_eff)}}}{{{fmt(b)}({money(v)} - {money(vc)})}} = {money(sv_req)} \\text{{ mm}} \\)</p>"
        
    if v >= 0.5 * vc:
        dia_c = max(top_dia, bot_dia)
        if Asc_req > 0:
            sv_max = min(0.75 * d, 300, 12 * dia_c)
            link_str += f"<p>For doubly reinforced:<br/>\\( S_{{v,max}} = 0.75d \\text{{, }} 300 \\text{{, or }} 12\\phi_c \\text{{ (whichever is lesser)}} \\)<br/>"
            link_str += f"\\( S_{{v,max}} = 0.75({fmt(d)}) \\text{{, }} 300 \\text{{, or }} 12({fmt(dia_c)}) = {fmt(sv_max)} \\text{{ mm}} \\)</p>"
        else:
            sv_max = min(0.75 * d, 300)
            link_str += f"<p>For singly reinforced:<br/>\\( S_{{v,max}} = 0.75d \\text{{ or }} 300 \\text{{ (whichever is lesser)}} \\)<br/>"
            link_str += f"\\( S_{{v,max}} = 0.75({fmt(d)}) \\text{{ or }} 300 = {fmt(sv_max)} \\text{{ mm}} \\)</p>"
        
        sv = min(sv_req, sv_max)
        sv = math.floor(sv / 25.0) * 25.0
        link_out = f"Provide 2-legs Y{int(link_dia)}mm bars @ {int(sv)}mm c/c"
        
    html_lines.append(row(bs8110.REF_SHEAR_LINKS, link_str, link_out))

    html_lines.append("<div class='section-drawing mt-4 border-t border-gray-200 pt-4 flex flex-col items-center'>")
    html_lines.append("<h5 class='text-md font-bold mb-2'>Beam section detailing (Maximum Moment Envelope)</h5>")
    
    html_lines.append("<div style='display: flex; flex-wrap: wrap; justify-content: center; gap: 2rem;'>")
    
    # Span detailing: Tension is bot_layer_counts (bottom), Compression is bot_layer_counts_c (top)
    html_lines.append("<div style='display: flex; flex-direction: column; align-items: center;'>")
    html_lines.append("<h6 class='text-sm font-semibold mb-1'>Span Detailing (Tension Bottom)</h6>")
    html_lines.append(draw_section_svg(b, h, cover, link_dia, bot_layer_counts, bot_dia, bot_layer_counts_c, bot_dia_c, False))
    html_lines.append("</div>")
    
    # Support detailing: Tension is top_layer_counts (top), Compression is top_layer_counts_c (bottom)
    html_lines.append("<div style='display: flex; flex-direction: column; align-items: center;'>")
    html_lines.append("<h6 class='text-sm font-semibold mb-1'>Support Detailing (Tension Top)</h6>")
    html_lines.append(draw_section_svg(b, h, cover, link_dia, top_layer_counts, top_dia, top_layer_counts_c, top_dia_c, True))
    html_lines.append("</div>")
    
    html_lines.append("</div>")
    html_lines.append("</div>")
    
    return "".join(html_lines)
