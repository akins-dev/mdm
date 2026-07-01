from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Tuple

from .core import Span, fmt, support_names
from .solver import (
    build_standard_distribution_rows,
    moment_distribution,
    analysis_from_final_moments,
    support_moment_rows
)


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
        udl = parse_float(span_payload.get("udl", "0") or "0", f"UDL for span {span_name}")
        if udl < 0:
            raise ValueError(f"UDL for span {span_name} cannot be negative.")
        point_loads = parse_point_loads(span_payload.get("point_loads", ""), length, span_name)
        spans.append(Span(left=left, right=right, length=length, udl=udl, point_loads=point_loads))

    fixed_supports = {supports[0], supports[-1]} if bool(payload.get("exterior_fixed", True)) else set()
    distribution_rows, distribution_factors, joint_ends, opposite = build_standard_distribution_rows(
        spans,
        supports,
        fixed_supports,
    )
    md_headers, md_rows, final_moments, cycles_used = moment_distribution(
        spans,
        supports,
        fixed_supports,
        distribution_factors,
        joint_ends,
        opposite,
        tolerance,
        max_cycles,
    )
    analysis = analysis_from_final_moments(spans, supports, final_moments)

    return {
        "status": (
            f"Calculated {len(spans)} span(s) across {support_count} supports. "
            f"Moment distribution completed in {cycles_used} cycle(s)."
        ),
        "tables": {
            "distribution": {
                "headers": ["Joints", "Member", "Stiffness (k)", "\\(\\Sigma k\\)", "DF"],
                "rows": distribution_rows,
            },
            "fem": {
                "headers": ["Span", "Load", "End", "Formula", "Substitution", "Moment (kNm)"],
                "rows": [row for span in spans for row in span.fixed_end_detail_rows()],
            },
            "moment": {"headers": md_headers, "rows": md_rows},
            "reactions": {
                "headers": ["Support", "Span", "Component", "Reaction (kN)"],
                "rows": analysis["reaction_rows"],
            },
            "support_reactions": {
                "headers": ["Support", "Total vertical reaction (kN)"],
                "rows": analysis["support_rows"],
            },
            "support_reaction_calculations": {
                "headers": ["Support", "Span-end reaction parts (kN)", "Summation", "Total reaction (kN)"],
                "rows": analysis["support_reaction_calc_rows"],
            },
            "reaction_calculations": {
                "headers": ["Span", "Calculation", "Formula", "Substitution", "Value (kN)"],
                "rows": analysis["reaction_calc_rows"],
            },
            "shear_calculations": {
                "headers": ["Span", "Formula", "Substitution"],
                "rows": analysis["shear_calc_rows"],
            },
            "bending_calculations": {
                "headers": ["Span", "Formula", "Substitution"],
                "rows": analysis["bending_calc_rows"],
            },
            "equilibrium_checks": {
                "headers": ["Location", "Check", "Formula", "Substitution", "Residual", "Status"],
                "rows": analysis["equilibrium_rows"],
            },
            "extrema": {
                "headers": ["Result", "Span", "Distance from left support (m)", "Value"],
                "rows": analysis["extrema_rows"],
            },
            "shear_values": {
                "headers": ["Span", "Local l (m)", "Global l (m)", "Shear V (kN)"],
                "rows": analysis["shear_value_rows"],
            },
            "moment_values": {
                "headers": ["Span", "Local x (m)", "Global x (m)", "Bending moment M (kNm)"],
                "rows": analysis["moment_value_rows"],
            },
            "extrema_summary": {
                "headers": ["Result", "Span", "x from left support (m)", "Value"],
                "rows": analysis["summary_rows"],
            },
            "support": {
                "headers": ["Support", "Member-end moments (kNm)", "Algebraic joint sum (kNm)"],
                "rows": support_moment_rows(supports, joint_ends, final_moments),
            },
        },
        "diagrams": analysis["diagrams"],
        "beam": analysis["beam"],
    }


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
        if self.path != "/calculate":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            result = calculate_from_payload(payload)
            self.send_json(200, result)
        except (json.JSONDecodeError, ValueError) as error:
            self.send_json(400, {"error": str(error)})

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
