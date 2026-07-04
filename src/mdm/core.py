from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any
import math

@dataclass
class Span:
    left: str
    right: str
    length: float
    udls: List[Tuple[float, float, float]] = field(default_factory=list)
    point_loads: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.left}{self.right}"

    @property
    def stiffness(self) -> float:
        return 1.0 / self.length

    @property
    def left_end(self) -> str:
        return f"{self.left}{self.right}"

    @property
    def right_end(self) -> str:
        return f"{self.right}{self.left}"

    def fixed_end_moments(self) -> Tuple[float, float]:
        """Return fixed-end moments (left end, right end).
        
        For a partial UDL of intensity w from position a to b on a span of length L:
          M_L = -(w / L^2) * [ (L/3)(b^3 - a^3) - (1/4)(b^4 - a^4) ]
          M_R =  (w / L^2) * [ (1/4)(b^4 - a^4) - (a/3)(b^3 - a^3) ]
        
        For a full-span UDL (a=0, b=L), these reduce to -wL^2/12 and +wL^2/12.
        """
        L = self.length
        fem_left = 0.0
        fem_right = 0.0

        for w, a, b in self.udls:
            b3_a3 = b**3 - a**3
            b4_a4 = b**4 - a**4
            fem_left += -(w / L**2) * (L * b3_a3 / 3.0 - b4_a4 / 4.0)
            fem_right += (w / L**2) * (b4_a4 / 4.0 - a * b3_a3 / 3.0)

        for load, a in self.point_loads:
            b = self.length - a
            fem_left += -(load * b**2 * a) / self.length**2
            fem_right += (load * a**2 * b) / self.length**2

        return fem_left, fem_right

    def _is_full_span_udl(self, a: float, b: float) -> bool:
        """Check if a UDL covers the entire span."""
        return math.isclose(a, 0.0, abs_tol=1e-9) and math.isclose(b, self.length, abs_tol=1e-9)

    def fixed_end_detail_rows(self) -> List[List[Any]]:
        rows: List[List[Any]] = []
        base_rows = 2 * len(self.udls) + 2 * len(self.point_loads)
        total_rows = 2 if base_rows == 0 else (base_rows + (2 if base_rows > 2 else 0))
        
        span_val = {"value": self.name, "rowspan": total_rows}
        L = self.length

        for udl_idx, (w, a, b) in enumerate(self.udls, start=1):
            if self._is_full_span_udl(a, b):
                # Full-span UDL — use the simple wL²/12 display
                left_value = -(w * L**2) / 12.0
                right_value = (w * L**2) / 12.0
                label = "UDL" if len(self.udls) == 1 else f"UDL {udl_idx}"
                rows.append(
                    [
                        span_val,
                        {"value": label, "rowspan": 2},
                        self.left_end,
                        "\\(-wL^2/12\\)",
                        f"\\(-({fmt(w)} \\times {fmt(L)}^2) / 12\\)",
                        money(left_value),
                    ]
                )
                span_val = None
                rows.append(
                    [
                        span_val,
                        None,
                        self.right_end,
                        "\\(wL^2/12\\)",
                        f"\\(({fmt(w)} \\times {fmt(L)}^2) / 12\\)",
                        money(right_value),
                    ]
                )
            else:
                # Partial UDL — use the general formula display
                b3_a3 = b**3 - a**3
                b4_a4 = b**4 - a**4
                left_value = -(w / L**2) * (L * b3_a3 / 3.0 - b4_a4 / 4.0)
                right_value = (w / L**2) * (b4_a4 / 4.0 - a * b3_a3 / 3.0)
                label = f"UDL {udl_idx}" if len(self.udls) > 1 else "UDL"
                range_str = f"({fmt(a)}m–{fmt(b)}m)"
                rows.append(
                    [
                        span_val,
                        {"value": f"{label} {range_str}", "rowspan": 2},
                        self.left_end,
                        "\\(-\\frac{w}{L^2}[\\frac{L}{3}(b^3-a^3)-\\frac{1}{4}(b^4-a^4)]\\)",
                        f"\\(-\\frac{{{fmt(w)}}}{{{fmt(L)}}}^2[\\frac{{{fmt(L)}}}{{3}}({fmt(b)}^3-{fmt(a)}^3)-\\frac{{1}}{{4}}({fmt(b)}^4-{fmt(a)}^4)]\\)",
                        money(left_value),
                    ]
                )
                span_val = None
                rows.append(
                    [
                        span_val,
                        None,
                        self.right_end,
                        "\\(\\frac{w}{L^2}[\\frac{1}{4}(b^4-a^4)-\\frac{a}{3}(b^3-a^3)]\\)",
                        f"\\(\\frac{{{fmt(w)}}}{{{fmt(L)}}}^2[\\frac{{1}}{{4}}({fmt(b)}^4-{fmt(a)}^4)-\\frac{{{fmt(a)}}}{{3}}({fmt(b)}^3-{fmt(a)}^3)]\\)",
                        money(right_value),
                    ]
                )

        for index, (load, a) in enumerate(self.point_loads, start=1):
            b = self.length - a
            left_value = -(load * b**2 * a) / self.length**2
            right_value = (load * a**2 * b) / self.length**2
            rows.append(
                [
                    span_val,
                    {"value": f"Point {index}", "rowspan": 2},
                    self.left_end,
                    "\\(-Pab^2/L^2\\)",
                    f"\\(-({fmt(load)} \\times {fmt(a)} \\times {fmt(b)}^2) / {fmt(self.length)}^2\\)",
                    money(left_value),
                ]
            )
            span_val = None
            rows.append(
                [
                    span_val,
                    None,
                    self.right_end,
                    "\\(Pa^2b/L^2\\)",
                    f"\\(({fmt(load)} \\times {fmt(a)}^2 \\times {fmt(b)}) / {fmt(self.length)}^2\\)",
                    money(right_value),
                ]
            )

        if not rows:
            rows.append([span_val, {"value": "No load", "rowspan": 2}, self.left_end, "\\(0\\)", "\\(0\\)", money(0.0)])
            span_val = None
            rows.append([span_val, None, self.right_end, "\\(0\\)", "\\(0\\)", money(0.0)])

        left_total, right_total = self.fixed_end_moments()
        if len(rows) > 2:
            rows.append([span_val, {"value": "Total", "rowspan": 2}, self.left_end, "\\(\\Sigma M_L\\)", "sum of left-end contributions", money(left_total)])
            span_val = None
            rows.append([span_val, None, self.right_end, "\\(\\Sigma M_R\\)", "sum of right-end contributions", money(right_total)])
            
        return rows


def support_names(count: int) -> List[str]:
    names = []
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(count):
        if i < len(alphabet):
            names.append(alphabet[i])
        else:
            names.append(f"S{i + 1}")
    return names


def money(value: float) -> str:
    if abs(value) < 0.0000005:
        value = 0.0
    return f"{value:,.4f}"


def fmt(value: float) -> str:
    return f"{value:g}"

STANDARD_BAR_AREAS = {
    6: [28.3, 56.6, 84.9, 113, 142, 170, 198, 226, 255, 283],
    8: [50.3, 101, 151, 201, 252, 302, 352, 402, 453, 503],
    10: [78.5, 157, 236, 314, 393, 471, 550, 628, 707, 785],
    12: [113, 226, 339, 452, 566, 679, 792, 905, 1020, 1130],
    16: [201, 402, 603, 804, 1010, 1210, 1410, 1610, 1810, 2010],
    20: [314, 628, 943, 1260, 1570, 1890, 2200, 2510, 2830, 3140],
    25: [491, 982, 1470, 1960, 2450, 2950, 3440, 3930, 4420, 4910],
    32: [804, 1610, 2410, 3220, 4020, 4830, 5630, 6430, 7240, 8040],
    40: [1260, 2510, 3770, 5030, 6280, 7540, 8800, 10100, 11300, 12600],
    50: [1960, 3930, 5890, 7850, 9820, 11800, 13700, 15700, 17700, 19600]
}

def get_bar_area(diameter: int, count: int = 1) -> float:
    if diameter in STANDARD_BAR_AREAS and 1 <= count <= 10:
        return STANDARD_BAR_AREAS[diameter][count - 1]
    return count * math.pi * (diameter ** 2) / 4.0

def select_bar_arrangement(required_area: float, b: float, cover: float, link_dia: float, max_agg_size: float = 20.0, is_compression: bool = False, target_dia: int = None) -> Tuple[List[int], int, float]:
    """
    Find the optimal bar arrangement (layer_counts, diameter, area_provided) that provides at least the required area
    and satisfies the spacing requirements in 1 or 2 layers.
    Returns (layer_counts, diameter, area_provided) or ([], 0, 0.0) if none found.
    """
    best_arrangement = None
    min_area_surplus = float('inf')
    
    if is_compression:
        dias_to_try = [12, 16, 20]
    else:
        dias_to_try = [20, 25, 16]
        
    if target_dia and target_dia in STANDARD_BAR_AREAS:
        if target_dia in dias_to_try:
            dias_to_try.remove(target_dia)
        dias_to_try.insert(0, target_dia)
        
    for dia in dias_to_try:
        count = 2 # Minimum 2 bars
        area_provided = 0.0
        while count <= 20:
            area_provided = get_bar_area(dia, count)
            if area_provided >= required_area:
                break
            count += 1
        
        if count > 20 or area_provided < required_area:
            continue
            
        min_spacing = max(max_agg_size + 5.0, float(dia))
        available_width = b - 2 * cover - 2 * link_dia
        
        max_n_layer = int((available_width + min_spacing) // (dia + min_spacing))
        
        if max_n_layer < 2:
            continue
            
        if count <= max_n_layer:
            layer_counts = [count]
        elif count <= 2 * max_n_layer:
            l1 = max_n_layer
            l2 = count - max_n_layer
            if l2 < 2:
                if l1 > 2:
                    l1 -= 1
                    l2 += 1
                else:
                    continue
            layer_counts = [l1, l2]
        else:
            continue
            
        surplus = area_provided - required_area
        penalty = 0.0 if len(layer_counts) == 1 else required_area * 0.1
        
        if (surplus + penalty) < min_area_surplus:
            min_area_surplus = surplus + penalty
            best_arrangement = (layer_counts, dia, area_provided)
                
    if best_arrangement:
        return best_arrangement
    return [], 0, 0.0

