from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Tuple

from .models.beam import Span, fmt, support_names
from .analyzers import ContinuousAnalyzer
from .design.design import design_section


def get_html_template() -> str:
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'index.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def parse_float(raw: object, label: str) -> float:
    try:
        return float(str(raw).strip())
    except ValueError as error:
        raise ValueError(f"{label} must be a number.") from error


def parse_point_loads(raw: object, length: float, span_name: str) -> List[Tuple[float, float]]:
    text = str(raw or "").strip()
    loads: List[Tuple[float, float]] = []
    if not text:
        return loads

    for part in text.split(";"):
        item = part.strip()
        if not item:
            continue
        if "@" not in item:
            raise ValueError(f"Point load '{item}' on span {span_name} must use P@a format.")
        load_text, distance_text = item.split("@", 1)
        load = parse_float(load_text, f"Point load magnitude on span {span_name}")
        distance = parse_float(distance_text, f"Point load distance on span {span_name}")
        if load < 0:
            raise ValueError(f"Point load magnitude on span {span_name} cannot be negative.")
        if distance < 0 or distance > length:
            raise ValueError(f"Point load distance on span {span_name} must be between 0 and {fmt(length)}.")
        loads.append((load, distance))
    return loads


def parse_udls(raw: object, length: float, span_name: str) -> List[Tuple[float, float, float]]:
    """Parse UDL string. Supports:
    - Plain number: '15' (full-span UDL, equivalent to 15@0-L)
    - Partial UDLs: '15@0-3; 20@4-6'
    Returns list of (w, start, end) tuples.
    """
    text = str(raw or "").strip()
    if not text or text == "0":
        return []

    udls: List[Tuple[float, float, float]] = []
    for part in text.split(";"):
        item = part.strip()
        if not item:
            continue
        if "@" in item:
            w_text, range_text = item.split("@", 1)
            if "-" not in range_text:
                raise ValueError(f"UDL '{item}' on span {span_name} must use w@start-end format.")
            start_text, end_text = range_text.split("-", 1)
            w = parse_float(w_text, f"UDL intensity on span {span_name}")
            start = parse_float(start_text, f"UDL start position on span {span_name}")
            end = parse_float(end_text, f"UDL end position on span {span_name}")
        else:
            w = parse_float(item, f"UDL intensity on span {span_name}")
            start = 0.0
            end = length

        if w < 0:
            raise ValueError(f"UDL intensity on span {span_name} cannot be negative.")
        if w == 0:
            continue
        if start < 0 or end > length + 1e-9:
            raise ValueError(f"UDL range on span {span_name} must be within 0 and {fmt(length)}.")
        if start >= end:
            raise ValueError(f"UDL start must be less than end on span {span_name}.")
        udls.append((w, start, min(end, length)))

    # Sort by start position and check for overlaps
    udls.sort(key=lambda x: x[1])
    for i in range(len(udls) - 1):
        if udls[i][2] > udls[i + 1][1] + 1e-9:
            raise ValueError(
                f"Overlapping UDLs on span {span_name}: "
                f"{fmt(udls[i][0])}@{fmt(udls[i][1])}-{fmt(udls[i][2])} overlaps with "
                f"{fmt(udls[i+1][0])}@{fmt(udls[i+1][1])}-{fmt(udls[i+1][2])}."
            )
    return udls


def calculate_from_payload(payload: Dict[str, object]) -> Dict[str, object]:
    support_count = int(parse_float(payload.get("support_count", ""), "Number of supports"))
    if support_count < 2:
        raise ValueError("Number of supports must be at least 2.")

    tolerance = parse_float(payload.get("tolerance", "0.0001"), "Tolerance")
    max_cycles = int(parse_float(payload.get("max_cycles", "50"), "Maximum cycles"))
    if tolerance < 0:
        raise ValueError("Tolerance cannot be negative.")
    if max_cycles < 1:
        raise ValueError("Maximum cycles must be at least 1.")

    span_payloads = payload.get("spans", [])
    if not isinstance(span_payloads, list) or len(span_payloads) != support_count - 1:
        raise ValueError("The number of span input rows must be one less than the number of supports.")

    supports = support_names(support_count)
    spans: List[Span] = []
    for index, span_payload in enumerate(span_payloads):
        if not isinstance(span_payload, dict):
            raise ValueError("Each span input must be an object.")
        left = supports[index]
        right = supports[index + 1]
        span_name = f"{left}{right}"
        length = parse_float(span_payload.get("length", ""), f"Length for span {span_name}")
        if length <= 0:
            raise ValueError(f"Length for span {span_name} must be greater than 0.")
        udls = parse_udls(span_payload.get("udls", span_payload.get("udl", "0")), length, span_name)
        point_loads = parse_point_loads(span_payload.get("point_loads", ""), length, span_name)
        spans.append(Span(left=left, right=right, length=length, udls=udls, point_loads=point_loads))

    fixed_supports = {supports[0], supports[-1]} if bool(payload.get("exterior_fixed", True)) else set()
    
    beam_type = payload.get("beam_type", "continuous").lower()
    overhang_type = payload.get("overhang_type", "left").lower()
    
    from .analyzers.overhanging import OverhangingAnalyzer
    from .analyzers.simply_supported import SimplySupportedAnalyzer
    from .analyzers.cantilever import CantileverAnalyzer
    
    if beam_type == "overhanging":
        analyzer = OverhangingAnalyzer(overhang_type=overhang_type)
    elif beam_type == "simply_supported":
        analyzer = SimplySupportedAnalyzer()
    elif beam_type == "cantilever":
        analyzer = CantileverAnalyzer()
    else:
        analyzer = ContinuousAnalyzer()
        
    return analyzer.analyze(
        spans=spans,
        supports=supports,
        fixed_supports=list(fixed_supports),
        tolerance=tolerance,
        max_cycles=max_cycles
    )


class MomentDistributionHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/", "/index.html"}:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(get_html_template().encode("utf-8"))

    def do_POST(self) -> None:
        if self.path == "/calculate":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                result = calculate_from_payload(payload)
                self.send_json(200, result)
            except (json.JSONDecodeError, ValueError) as error:
                self.send_json(400, {"error": str(error)})
            return
            
        if self.path == "/design":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                
                # Payload contains analysis_results and design_params
                analysis = payload.get("analysis_results", {})
                params = payload.get("design_params", {})
                
                fcu = float(params.get("fcu", 30))
                fy = float(params.get("fy", 460))
                fyv = float(params.get("fyv", 250))
                b = float(params.get("b", 230))
                h = float(params.get("h", 450))
                cover = float(params.get("cover", 30))
                main_bar_dia = float(params.get("main_bar_dia", 20))
                link_dia = float(params.get("link_dia", 10))
                support_cond = params.get("support_cond", "Continuous")
                
                reports = []
                
                # Group extrema rows by span and find max moment and max shear for each span
                extrema_rows = analysis.get("tables", {}).get("extrema", {}).get("rows", [])
                
                spans = {}
                for row in extrema_rows:
                    span_name = row[0]
                    # row: [span_name, l_val, shear, moment]
                    # Since these are strings representing formatted numbers, we need to parse them
                    # Actually, the analysis_from_final_moments function in solver.py returns money formatted strings
                    # We can use the diagrams data or parse the strings, but wait, the analysis payload also includes "diagrams"
                    # But it's easier to just re-fetch the max moment and shear from the raw data if we pass the raw data
                    pass
                
                # To get raw floats, let's use the 'beam' data from analysis
                beam_data = analysis.get("beam", {})
                span_infos = beam_data.get("spans", [])
                
                span_tasks = []
                for span_info in span_infos:
                    span_name = span_info.get("name")
                    moment_values = analysis.get("tables", {}).get("moment_values", {}).get("rows", [])
                    shear_values = analysis.get("tables", {}).get("shear_values", {}).get("rows", [])
                    
                    max_sagging_moment = 0.0
                    max_hogging_moment = 0.0
                    for row in moment_values:
                        if str(row[0]) == span_name:
                            m_val = float(str(row[3]).replace(',', ''))
                            if m_val > max_sagging_moment:
                                max_sagging_moment = m_val
                            if m_val < max_hogging_moment:
                                max_hogging_moment = m_val
                                
                    max_abs_shear = 0.0
                    for row in shear_values:
                        if str(row[0]) == span_name:
                            v_val = abs(float(str(row[3]).replace(',', '')))
                            if v_val > max_abs_shear:
                                max_abs_shear = v_val
                                
                    if max_sagging_moment > 0.0:
                        span_tasks.append({
                            "name": span_name,
                            "M": max_sagging_moment,
                            "V": max_abs_shear,
                            "is_support": False,
                            "span_length_mm": float(span_info.get("length", 0)) * 1000.0,
                            "support_cond": support_cond
                        })
                    elif max_hogging_moment < -0.01:
                        # Uplifted span: entirely hogging, no sagging moment exists
                        span_tasks.append({
                            "name": span_name,
                            "M": max_hogging_moment,
                            "V": max_abs_shear,
                            "is_support": True,
                            "span_length_mm": float(span_info.get("length", 0)) * 1000.0,
                            "support_cond": support_cond,
                            "is_uplifted": True
                        })

                support_tasks = []
                for span_info in span_infos:
                    ml = float(span_info.get("ml", 0))
                    if ml < -0.01:
                        max_abs_shear = abs(float(span_info.get("left_reaction", 0)))
                        # Ensure we don't add duplicate inner supports (they share the same label)
                        name = f"Support {span_info.get('left')}"
                        if not any(t["name"] == name for t in support_tasks):
                            support_tasks.append({
                                "name": name,
                                "M": ml,
                                "V": max_abs_shear,
                                "is_support": True
                            })
                        
                    if span_info == span_infos[-1]:
                        mr = float(span_info.get("mr", 0))
                        if mr < -0.01:
                            max_abs_shear = abs(float(span_info.get("right_reaction", 0)))
                            name = f"Support {span_info.get('right')}"
                            if not any(t["name"] == name for t in support_tasks):
                                support_tasks.append({
                                    "name": name,
                                    "M": mr,
                                    "V": max_abs_shear,
                                    "is_support": True
                                })
                
                all_tasks = span_tasks + support_tasks
                
                if all_tasks:
                    global_V = max(t["V"] for t in all_tasks)
                    
                    pos_tasks = [t for t in all_tasks if t["M"] >= 0]
                    neg_tasks = [t for t in all_tasks if t["M"] < 0]
                    
                    max_pos_task = max(pos_tasks, key=lambda t: t["M"]) if pos_tasks else None
                    max_neg_task = min(neg_tasks, key=lambda t: t["M"]) if neg_tasks else None

                    envelope_tasks = []
                    
                    combined_notes = [
                        "Top reinforcement is designed using the maximum negative (hogging) moment from the envelope.",
                        "Bottom reinforcement is designed using the maximum positive (sagging) moment from the envelope.",
                        "Stirrups are designed using the maximum shear force from the shear envelope.",
                        "This ensures the beam is safe under all possible loading arrangements, not just one."
                    ]
                    
                    if max_pos_task:
                        task_pos = {
                            "name": "Global Envelope - Maximum Positive (Sagging) Moment",
                            "M": max_pos_task["M"],
                            "V": global_V,
                            "is_support": False,
                            "highlight_title": "DESIGN FOR MAXIMUM SAGGING VALUES",
                            "bg_color": "",
                            "show_position": True,
                            "span_length_mm": max([t.get("span_length_mm", 0.0) for t in span_tasks] + [0.0]),
                            "support_cond": support_cond,
                            "notes": None,
                            "is_envelope": True
                        }
                    else:
                        task_pos = None

                    if max_neg_task:
                        task_neg = {
                            "name": "Global Envelope - Maximum Negative (Hogging) Moment",
                            "M": max_neg_task["M"],
                            "V": global_V,
                            "is_support": True,
                            "highlight_title": "DESIGN FOR MAXIMUM HOGGING VALUES",
                            "bg_color": "",
                            "show_position": True,
                            "span_length_mm": max([t.get("span_length_mm", 0.0) for t in span_tasks] + [0.0]),
                            "support_cond": support_cond,
                            "notes": None,
                            "is_envelope": True
                        }
                    else:
                        task_neg = None

                    # Assign green bg to the overall max, amber to the other
                    if task_pos and task_neg:
                        if abs(task_pos["M"]) >= abs(task_neg["M"]):
                            task_pos["name"] += " [OVERALL MAX]"
                            task_pos["highlight_title"] += " [OVERALL MAX]"
                            task_pos["notes"] = combined_notes
                            task_pos["bg_color"] = "#f0fdf4"
                            task_pos["is_overall_max"] = True
                            task_neg["bg_color"] = "#fffbeb"
                            task_neg["is_overall_max"] = False
                            envelope_tasks = [task_pos, task_neg]
                        else:
                            task_neg["name"] += " [OVERALL MAX]"
                            task_neg["highlight_title"] += " [OVERALL MAX]"
                            task_neg["notes"] = combined_notes
                            task_neg["bg_color"] = "#f0fdf4"
                            task_neg["is_overall_max"] = True
                            task_pos["bg_color"] = "#fffbeb"
                            task_pos["is_overall_max"] = False
                            envelope_tasks = [task_neg, task_pos]
                    elif task_pos:
                        task_pos["name"] += " [OVERALL MAX]"
                        task_pos["highlight_title"] += " [OVERALL MAX]"
                        task_pos["notes"] = combined_notes
                        task_pos["bg_color"] = "#f0fdf4"
                        task_pos["is_overall_max"] = True
                        envelope_tasks = [task_pos]
                    elif task_neg:
                        task_neg["name"] += " [OVERALL MAX]"
                        task_neg["highlight_title"] += " [OVERALL MAX]"
                        task_neg["notes"] = combined_notes
                        task_neg["bg_color"] = "#f0fdf4"
                        task_neg["is_overall_max"] = True
                        envelope_tasks = [task_neg]

                    for env_task in reversed(envelope_tasks):
                        all_tasks.insert(0, env_task)

                from .design import shear_and_drawing_section
                
                env_count = len([t for t in all_tasks if t.get("is_envelope")])
                processed_envs = 0
                
                top_layer_counts, top_dia = [], main_bar_dia
                top_layer_counts_c, top_dia_c = [], main_bar_dia
                bot_layer_counts, bot_dia = [], main_bar_dia
                bot_layer_counts_c, bot_dia_c = [], main_bar_dia
                env_area_prov = 0.0
                env_Asc_req = 0.0
                env_d = 0.0
                
                # Separate reports into categories
                overall_max_reports = []  # shown open
                other_envelope_reports = []  # collapsed by default
                individual_reports = []  # collapsed by default
                shear_detailing_html = ""

                for t in all_tasks:
                    is_env = t.get("is_envelope", False)
                    report = design_section(
                        name=t["name"],
                        M=t["M"],
                        V=t["V"],
                        is_support=t["is_support"],
                        fcu=fcu, fy=fy, fyv=fyv, b=b, h=h, cover=cover,
                        main_bar_dia=main_bar_dia, link_dia=link_dia,
                        span_length=t.get("span_length_mm", 0.0),
                        support_cond=t.get("support_cond", "Continuous"),
                        highlight_title=t.get("highlight_title", ""),
                        bg_color=t.get("bg_color", ""),
                        show_position=True if is_env else t.get("show_position", True),
                        notes=t.get("notes", None),
                        skip_shear=is_env,
                        skip_drawing=is_env,
                        is_uplifted=t.get("is_uplifted", False)
                    )
                    
                    if is_env:
                        processed_envs += 1
                        env_d = report["d"]
                        if t["is_support"]:
                            top_layer_counts = report["layer_counts"]
                            top_dia = report["dia"]
                            top_layer_counts_c = report["layer_counts_c"]
                            top_dia_c = report["dia_c"]
                            env_area_prov = max(env_area_prov, report["area_prov"])
                            env_Asc_req = max(env_Asc_req, report["Asc_req"])
                        else:
                            bot_layer_counts = report["layer_counts"]
                            bot_dia = report["dia"]
                            bot_layer_counts_c = report["layer_counts_c"]
                            bot_dia_c = report["dia_c"]
                            env_area_prov = max(env_area_prov, report["area_prov"])
                            env_Asc_req = max(env_Asc_req, report["Asc_req"])
                        
                        if t.get("is_overall_max"):
                            overall_max_reports.append(report["html"])
                        else:
                            other_envelope_reports.append(report["html"])
                            
                        if processed_envs == env_count:
                            shear_detailing_html = shear_and_drawing_section(
                                name="Global Envelope - Shear & Detailing",
                                V=global_V, b=b, h=h, d=env_d, cover=cover, fcu=fcu, fyv=fyv,
                                area_prov=env_area_prov, Asc_req=env_Asc_req, link_dia=link_dia,
                                top_layer_counts=top_layer_counts, top_dia=top_dia,
                                top_layer_counts_c=top_layer_counts_c, top_dia_c=top_dia_c,
                                bot_layer_counts=bot_layer_counts, bot_dia=bot_dia,
                                bot_layer_counts_c=bot_layer_counts_c, bot_dia_c=bot_dia_c,
                                highlight_title="GLOBAL SHEAR & DETAILING",
                                bg_color="#f8fafc"
                            )
                    else:
                        individual_reports.append(report["html"])
                
                # Assemble final reports list
                # 1. Overall max (shown open)
                for r in overall_max_reports:
                    reports.append(r)
                
                # 2. Other envelope design (collapsed)
                if other_envelope_reports:
                    other_env_html = "<details style='margin-top: 20px; margin-bottom: 20px;'>"
                    other_env_html += "<summary style='cursor: pointer; font-weight: 700; font-size: 1rem; padding: 10px 15px; background: #fffbeb; border: 1px solid #fbbf24; border-radius: 6px; color: #92400e;'>Other Envelope Design (Click to expand)</summary>"
                    other_env_html += "<div style='margin-top: 10px;'>"
                    for r in other_envelope_reports:
                        other_env_html += r
                    other_env_html += "</div></details>"
                    reports.append(other_env_html)

                # 3. Global shear & detailing (shown open)
                if shear_detailing_html:
                    reports.append(shear_detailing_html)
                
                # 4. Individual span & support designs (collapsed)
                if individual_reports:
                    indiv_html = "<details style='margin-top: 20px;'>"
                    indiv_html += "<summary style='cursor: pointer; font-weight: 700; font-size: 1rem; padding: 10px 15px; background: #f1f5f9; border: 1px solid #cbd5e1; border-radius: 6px; color: #334155;'>Individual Span & Support Designs (Click to expand)</summary>"
                    indiv_html += "<div style='margin-top: 10px;'>"
                    indiv_html += "<p style='color: #64748b; font-style: italic; margin-bottom: 15px;'>Calculated using their original, individual shear forces</p>"
                    for r in individual_reports:
                        indiv_html += r
                    indiv_html += "</div></details>"
                    reports.append(indiv_html)
                            
                self.send_json(200, {"reports": reports})
            except Exception as error:
                import traceback
                traceback.print_exc()
                self.send_json(400, {"error": str(error)})
            return

        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status_code: int, payload: Dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(host: str, preferred_port: int, attempts: int = 10) -> Tuple[ThreadingHTTPServer, int]:
    server = None
    port = preferred_port
    for candidate in range(preferred_port, preferred_port + attempts):
        try:
            server = ThreadingHTTPServer((host, candidate), MomentDistributionHandler)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        end_port = preferred_port + attempts - 1
        raise RuntimeError(f"Could not start the GUI server on ports {preferred_port} through {end_port}.")
    return server, port
