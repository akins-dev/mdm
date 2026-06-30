#!/usr/bin/env python3
"""Moment distribution method for continuous beams.

Sign convention used in this program:
    Clockwise member-end moments are positive.

Supported span loads:
    - uniformly distributed load over the full span
    - point load at any distance from the left support

Relative member stiffness is taken as 1/L, as requested.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List, Tuple


@dataclass
class Span:
    left: str
    right: str
    length: float
    udl: float = 0.0
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
        """Return fixed-end moments (left end, right end)."""
        fem_left = -(self.udl * self.length**2) / 12.0
        fem_right = (self.udl * self.length**2) / 12.0

        for load, a in self.point_loads:
            b = self.length - a
            fem_left += -(load * b**2 * a) / self.length**2
            fem_right += (load * a**2 * b) / self.length**2

        return fem_left, fem_right

    def fixed_end_detail_rows(self) -> List[List[str]]:
        rows: List[List[str]] = []
        if self.udl:
            left_value = -(self.udl * self.length**2) / 12.0
            right_value = (self.udl * self.length**2) / 12.0
            rows.append(
                [
                    self.name,
                    "UDL",
                    self.left_end,
                    "\\(-wL^2/12\\)",
                    f"\\(-({fmt(self.udl)} \\times {fmt(self.length)}^2) / 12\\)",
                    money(left_value),
                ]
            )
            rows.append(
                [
                    self.name,
                    "UDL",
                    self.right_end,
                    "\\(wL^2/12\\)",
                    f"\\(({fmt(self.udl)} \\times {fmt(self.length)}^2) / 12\\)",
                    money(right_value),
                ]
            )

        for index, (load, a) in enumerate(self.point_loads, start=1):
            b = self.length - a
            left_value = -(load * b**2 * a) / self.length**2
            right_value = (load * a**2 * b) / self.length**2
            rows.append(
                [
                    self.name,
                    f"Point {index}",
                    self.left_end,
                    "\\(-Pab^2/L^2\\)",
                    f"\\(-({fmt(load)} \\times {fmt(a)} \\times {fmt(b)}^2) / {fmt(self.length)}^2\\)",
                    money(left_value),
                ]
            )
            rows.append(
                [
                    self.name,
                    f"Point {index}",
                    self.right_end,
                    "\\(Pa^2b/L^2\\)",
                    f"\\(({fmt(load)} \\times {fmt(a)}^2 \\times {fmt(b)}) / {fmt(self.length)}^2\\)",
                    money(right_value),
                ]
            )

        if not rows:
            rows.append([self.name, "No load", self.left_end, "\\(0\\)", "\\(0\\)", money(0.0)])
            rows.append([self.name, "No load", self.right_end, "\\(0\\)", "\\(0\\)", money(0.0)])

        left_total, right_total = self.fixed_end_moments()
        if len(rows) > 2:
            rows.append([self.name, "Total", self.left_end, "\\(\\Sigma M_L\\)", "sum of left-end contributions", money(left_total)])
            rows.append([self.name, "Total", self.right_end, "\\(\\Sigma M_R\\)", "sum of right-end contributions", money(right_total)])
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


def build_distribution_rows(
    spans: List[Span],
    supports: List[str],
    fixed_supports: set[str],
) -> Tuple[List[List[str]], Dict[str, float], Dict[str, List[str]], Dict[str, str]]:
    joint_ends: Dict[str, List[str]] = {support: [] for support in supports}
    end_to_span: Dict[str, Span] = {}
    opposite: Dict[str, str] = {}

    for span in spans:
        joint_ends[span.left].append(span.left_end)
        joint_ends[span.right].append(span.right_end)
        end_to_span[span.left_end] = span
        end_to_span[span.right_end] = span
        opposite[span.left_end] = span.right_end
        opposite[span.right_end] = span.left_end

    distribution_factors: Dict[str, float] = {}
    rows: List[List[str]] = []

    for joint in supports:
        total_stiffness = 0.0 if joint in fixed_supports else sum(end_to_span[end].stiffness for end in joint_ends[joint])
        for end in joint_ends[joint]:
            span = end_to_span[end]
            df = 0.0 if total_stiffness == 0 else span.stiffness / total_stiffness
            distribution_factors[end] = df
            rows.append(
                [
                    joint,
                    span.name,
                    end,
                    money(span.stiffness),
                    money(total_stiffness),
                    money(df),
                ]
            )

    return rows, distribution_factors, joint_ends, opposite


def build_standard_distribution_rows(
    spans: List[Span],
    supports: List[str],
    fixed_supports: set[str],
) -> Tuple[List[List[str]], Dict[str, float], Dict[str, List[str]], Dict[str, str]]:
    rows, distribution_factors, joint_ends, opposite = build_distribution_rows(spans, supports, fixed_supports)
    standard_rows: List[List[str]] = []
    for joint, span_name, end, stiffness, joint_sum, df in rows:
        span = next(span for span in spans if span.name == span_name)
        standard_rows.append(
            [
                joint,
                end,
                f"\\(k=1/L=1/{fmt(span.length)}={stiffness}\\)",
                f"\\(\\Sigma k={joint_sum}\\)",
                f"\\(DF=k/\\Sigma k={df}\\)",
            ]
        )
    return standard_rows, distribution_factors, joint_ends, opposite


def moment_distribution(
    spans: List[Span],
    supports: List[str],
    fixed_supports: set[str],
    distribution_factors: Dict[str, float],
    joint_ends: Dict[str, List[str]],
    opposite: Dict[str, str],
    tolerance: float,
    max_cycles: int,
) -> Tuple[List[str], List[List[str]], Dict[str, float], int]:
    end_labels = [end for span in spans for end in (span.left_end, span.right_end)]
    moments = {end: 0.0 for end in end_labels}

    for span in spans:
        left_fem, right_fem = span.fixed_end_moments()
        moments[span.left_end] = left_fem
        moments[span.right_end] = right_fem

    end_to_joint = {end: joint for joint, ends in joint_ends.items() for end in ends}
    rows: List[List[str]] = [
        ["Joints"] + [end_to_joint[end] for end in end_labels],
        ["Members"] + end_labels,
        ["DF"] + [money(distribution_factors[end]) for end in end_labels],
        ["FEM"] + [money(moments[end]) for end in end_labels],
    ]

    cycles_used = 0
    for cycle in range(1, max_cycles + 1):
        cycles_used = cycle
        balance_row = {end: 0.0 for end in end_labels}
        carry_row = {end: 0.0 for end in end_labels}
        active_joints: List[str] = []

        for joint in supports:
            if joint in fixed_supports:
                continue

            unbalanced = sum(moments[end] for end in joint_ends[joint])
            if abs(unbalanced) <= tolerance:
                continue

            active_joints.append(joint)
            for end in joint_ends[joint]:
                distributed = -unbalanced * distribution_factors[end]
                balance_row[end] += distributed

        if not active_joints:
            break

        for end in end_labels:
            moments[end] += balance_row[end]

        for end in end_labels:
            carried = balance_row[end] * 0.5
            carry_row[opposite[end]] += carried
        for end in end_labels:
            moments[end] += carry_row[end]

        rows.append([f"Distribution cycle {cycle}"] + [money(balance_row[end]) for end in end_labels])
        rows.append([f"Carry over cycle {cycle}"] + [money(carry_row[end]) for end in end_labels])

        max_unbalanced = max(
            [abs(sum(moments[end] for end in joint_ends[joint])) for joint in supports if joint not in fixed_supports] or [0.0]
        )
        if max_unbalanced <= tolerance:
            break

    rows.append(["End Moment"] + [money(moments[end]) for end in end_labels])
    return ["Step"] + end_labels, rows, moments, cycles_used


def support_moment_rows(
    supports: List[str],
    joint_ends: Dict[str, List[str]],
    moments: Dict[str, float],
) -> List[List[str]]:
    rows = []
    for joint in supports:
        end_values = ", ".join(f"{end}={money(moments[end])}" for end in joint_ends[joint])
        rows.append([joint, end_values, money(sum(moments[end] for end in joint_ends[joint]))])
    return rows


def total_span_load(span: Span) -> float:
    return span.udl * span.length + sum(load for load, _distance in span.point_loads)


def load_moment_about_left(span: Span) -> float:
    return span.udl * span.length * (span.length / 2.0) + sum(load * distance for load, distance in span.point_loads)


def span_reactions(span: Span, final_moments: Dict[str, float]) -> Tuple[float, float]:
    total_load = total_span_load(span)
    moment_about_left = load_moment_about_left(span)
    left_moment = final_moments[span.left_end]
    right_moment = final_moments[span.right_end]
    right_reaction = (moment_about_left + left_moment + right_moment) / span.length
    left_reaction = total_load - right_reaction
    return left_reaction, right_reaction


def shear_at(span: Span, left_reaction: float, x: float, after_point_loads: bool = True) -> float:
    shear = left_reaction - span.udl * x
    for load, distance in span.point_loads:
        if distance < x or (after_point_loads and math.isclose(distance, x, abs_tol=1e-9)):
            shear -= load
    return shear


def moment_at(span: Span, final_moments: Dict[str, float], left_reaction: float, x: float) -> float:
    moment = final_moments[span.left_end] + left_reaction * x - (span.udl * x**2) / 2.0
    for load, distance in span.point_loads:
        if x >= distance:
            moment -= load * (x - distance)
    return moment


def span_station_candidates(span: Span, final_moments: Dict[str, float], left_reaction: float) -> List[float]:
    candidates = {0.0, span.length}
    for _load, distance in span.point_loads:
        candidates.add(distance)

    breakpoints = [0.0] + sorted({distance for _load, distance in span.point_loads if 0.0 < distance < span.length}) + [span.length]
    for start, end in zip(breakpoints, breakpoints[1:]):
        shear_start = shear_at(span, left_reaction, start, after_point_loads=True)
        if span.udl and start <= shear_start / span.udl + start <= end:
            root = start + shear_start / span.udl
            if 0.0 <= root <= span.length:
                candidates.add(root)

    return sorted(candidates)


def diagram_points(span: Span, final_moments: Dict[str, float], left_reaction: float, global_start: float) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    x_values = {0.0, span.length}
    key_x_values = set(span_station_candidates(span, final_moments, left_reaction))
    x_values.update(key_x_values)
    intervals = 48
    for index in range(intervals + 1):
        x_values.add(span.length * index / intervals)
    for _load, distance in span.point_loads:
        key_x_values.add(distance)
        x_values.add(max(0.0, distance - 1e-6))
        x_values.add(distance)
        x_values.add(min(span.length, distance + 1e-6))

    shear_points = []
    moment_points = []
    for x in sorted(x_values):
        shear_points.append(
            {
                "span": span.name,
                "local_x": x,
                "x": global_start + x,
                "y": shear_at(span, left_reaction, x, after_point_loads=True),
                "key": any(math.isclose(x, key_x, abs_tol=1e-6) for key_x in key_x_values),
            }
        )
        moment_points.append(
            {
                "span": span.name,
                "local_x": x,
                "x": global_start + x,
                "y": moment_at(span, final_moments, left_reaction, x),
                "key": any(math.isclose(x, key_x, abs_tol=1e-6) for key_x in key_x_values),
            }
        )
    return shear_points, moment_points


def analysis_from_final_moments(
    spans: List[Span],
    supports: List[str],
    final_moments: Dict[str, float],
) -> Dict[str, object]:
    reaction_rows: List[List[str]] = []
    reaction_calc_rows: List[List[str]] = []
    support_reaction_calc_rows: List[List[str]] = []
    shear_calc_rows: List[List[str]] = []
    bending_calc_rows: List[List[str]] = []
    extrema_rows: List[List[str]] = []
    equilibrium_rows: List[List[str]] = []
    support_reactions = {support: 0.0 for support in supports}
    support_reaction_parts = {support: [] for support in supports}
    shear_points: List[Dict[str, object]] = []
    moment_points: List[Dict[str, object]] = []
    support_positions: List[Dict[str, object]] = []
    span_infos: List[Dict[str, object]] = []
    joint_ends: Dict[str, List[str]] = {support: [] for support in supports}
    for span in spans:
        joint_ends[span.left].append(span.left_end)
        joint_ends[span.right].append(span.right_end)

    global_x = 0.0
    max_shear = {"span": "", "x": 0.0, "value": 0.0}
    max_moment = {"span": "", "x": 0.0, "value": 0.0}

    support_positions.append({"name": supports[0], "x": global_x})
    shear_points.append({"span": "Start", "local_x": 0.0, "x": 0.0, "y": 0.0, "key": True})
    for span in spans:
        span_start = global_x
        left_reaction, right_reaction = span_reactions(span, final_moments)
        support_reactions[span.left] += left_reaction
        support_reactions[span.right] += right_reaction
        support_reaction_parts[span.left].append((span.name, left_reaction))
        support_reaction_parts[span.right].append((span.name, right_reaction))

        total_load = total_span_load(span)
        load_moment = load_moment_about_left(span)
        reaction_calc_rows.append(
            [
                span.name,
                "Right reaction",
                "\\(R_R=(\\Sigma W x + M_L + M_R)/L\\)",
                (
                    f"\\(({money(load_moment)} + {money(final_moments[span.left_end])} + "
                    f"{money(final_moments[span.right_end])})/{fmt(span.length)}\\)"
                ),
                money(right_reaction),
            ]
        )
        reaction_calc_rows.append(
            [
                span.name,
                "Left reaction",
                "\\(R_L=\\Sigma W-R_R\\)",
                f"\\({money(total_load)} - {money(right_reaction)}\\)",
                money(left_reaction),
            ]
        )

        station_candidates = span_station_candidates(span, final_moments, left_reaction)
        for x in station_candidates:
            shear = shear_at(span, left_reaction, x, after_point_loads=True)
            moment = moment_at(span, final_moments, left_reaction, x)
            if abs(moment) > abs(max_moment["value"]):
                max_moment = {"span": span.name, "x": x, "value": moment}
            extrema_rows.append([span.name, money(x), money(shear), money(moment)])

        shear_checks = [(0.0, True), (span.length, True)]
        for _load, distance in span.point_loads:
            shear_checks.append((distance, False))
            shear_checks.append((distance, True))
        for x, after_point_loads in shear_checks:
            shear = shear_at(span, left_reaction, x, after_point_loads=after_point_loads)
            if abs(shear) > abs(max_shear["value"]):
                max_shear = {"span": span.name, "x": x, "value": shear}

        shear_calc_rows.append(
            [
                span.name,
                "\\(V(l)=R_L-wl-\\Sigma P_{a\\le l}\\)",
                f"\\(V(l)={money(left_reaction)}-{money(span.udl)}l-\\Sigma P\\)",
            ]
        )
        for l_val in station_candidates:
            point_load_sum = sum(load for load, distance in span.point_loads if distance <= l_val)
            l_str = f"\\frac{{{money(span.length)}}}{{2}}" if math.isclose(l_val, span.length / 2, abs_tol=1e-6) else money(l_val)
            shear_calc_rows.append(
                [
                    f"{span.name} at l={l_str}",
                    "\\(V=R_L-wl-\\Sigma P\\)",
                    f"\\({money(left_reaction)}-{money(span.udl)}({l_str})-{money(point_load_sum)}={money(shear_at(span, left_reaction, l_val))}\\)",
                ]
            )
        bending_calc_rows.append(
            [
                span.name,
                "\\(M(l)=M_{prev}+\\text{Area of SFD}\\)",
                "\\(M(l)=M_{prev} + \\frac{1}{2}(V_{start} + V_{end})\\Delta l\\)",
            ]
        )
        
        stations = sorted(list(set(station_candidates)))
        prev_l = 0.0
        prev_M = final_moments[span.left_end]
        
        bending_calc_rows.append(
            [
                f"{span.name} at l=0",
                "\\(M(0)=M_L\\)",
                f"\\({money(prev_M)}\\)",
            ]
        )
        
        for l_val in stations:
            if l_val == 0.0:
                continue
            
            v_start = shear_at(span, left_reaction, prev_l, after_point_loads=True)
            v_end = shear_at(span, left_reaction, l_val, after_point_loads=False)
            dl = l_val - prev_l
            area = 0.5 * (v_start + v_end) * dl
            current_M = prev_M + area
            
            dl_str = f"\\frac{{{money(span.length)}}}{{2}}" if math.isclose(dl, span.length / 2, abs_tol=1e-6) else money(dl)
            l_str = f"\\frac{{{money(span.length)}}}{{2}}" if math.isclose(l_val, span.length / 2, abs_tol=1e-6) else money(l_val)
            prev_l_str = f"\\frac{{{money(span.length)}}}{{2}}" if math.isclose(prev_l, span.length / 2, abs_tol=1e-6) else money(prev_l)
            
            if span.udl == 0 and math.isclose(v_start, v_end, abs_tol=1e-6):
                area_term = f"{money(v_start)}({dl_str})"
            else:
                area_term = f"\\frac{{1}}{{2}}({money(v_start)} + {money(v_end)})({dl_str})"
                
            bending_calc_rows.append(
                [
                    f"{span.name} at l={l_str}",
                    f"\\(M({l_str}) = M({prev_l_str}) + \\text{{Area}}\\)",
                    f"\\({money(prev_M)} + {area_term} = {money(current_M)}\\)",
                ]
            )
            prev_l = l_val
            prev_M = current_M

        span_shear_points, span_moment_points = diagram_points(span, final_moments, left_reaction, global_x)
        shear_points.extend(span_shear_points)
        moment_points.extend(span_moment_points)
        global_x += span.length
        support_positions.append({"name": span.right, "x": global_x})
        span_infos.append(
            {
                "name": span.name,
                "left": span.left,
                "right": span.right,
                "length": span.length,
                "start": span_start,
                "end": global_x,
                "udl": span.udl,
                "point_loads": [{"load": load, "distance": distance} for load, distance in span.point_loads],
                "left_reaction": left_reaction,
                "right_reaction": right_reaction,
                "ml": final_moments[span.left_end],
                "mr": final_moments[span.right_end],
                "load_moment": load_moment,
                "total_load": total_load,
            }
        )

        reaction_rows.append([span.left, span.name, "Left span-end reaction", money(left_reaction)])
        reaction_rows.append([span.right, span.name, "Right span-end reaction", money(right_reaction)])
        shear_closure = left_reaction + right_reaction - total_load
        right_before_support = shear_at(span, left_reaction, span.length, after_point_loads=True)
        right_after_support = right_before_support + right_reaction
        equilibrium_rows.append(
            [
                span.name,
                "Vertical shear closure",
                "\\(R_L+R_R-\\Sigma W\\)",
                f"\\({money(left_reaction)}+{money(right_reaction)}-{money(total_load)}\\)",
                money(shear_closure),
                "Balanced" if abs(shear_closure) < 1e-6 else "Unbalanced",
            ]
        )
        equilibrium_rows.append(
            [
                span.name,
                "SFD right support closure",
                "\\(V(L^-)+R_R\\)",
                f"\\({money(right_before_support)}+{money(right_reaction)}\\)",
                money(right_after_support),
                "Balanced" if abs(right_after_support) < 1e-6 else "Unbalanced",
            ]
        )

    support_rows = [[support, money(support_reactions[support])] for support in supports]
    for support in supports:
        parts = support_reaction_parts[support]
        if not parts:
            continue
        support_reaction_calc_rows.append(
            [
                support,
                " + ".join(f"{span_name}: {money(value)}" for span_name, value in parts),
                "\\(" + "+".join(money(value) for _span_name, value in parts) + "\\)",
                money(support_reactions[support]),
            ]
        )

    shear_points.append({"span": "End", "local_x": 0.0, "x": global_x, "y": 0.0, "key": True})
    total_support_reaction = sum(support_reactions.values())
    total_load_all_spans = sum(total_span_load(span) for span in spans)
    equilibrium_rows.append(
        [
            "Whole beam",
            "Global vertical shear closure",
            "\\(\\Sigma R-\\Sigma W\\)",
            f"\\({money(total_support_reaction)}-{money(total_load_all_spans)}\\)",
            money(total_support_reaction - total_load_all_spans),
            "Balanced" if abs(total_support_reaction - total_load_all_spans) < 1e-6 else "Unbalanced",
        ]
    )
    for support in supports:
        residual = sum(final_moments[end] for end in joint_ends[support])
        is_exterior_support = support in {supports[0], supports[-1]}
        status = "Fixed-end support moment" if is_exterior_support and abs(residual) >= 1e-4 else ("Balanced" if abs(residual) < 1e-4 else "Residual moment remains")
        equilibrium_rows.append(
            [
                support,
                "Residual joint moment",
                "\\(\\Sigma M_{joint}\\)",
                "\\(" + "+".join(money(final_moments[end]) for end in joint_ends[support]) + "\\)",
                money(residual),
                status,
            ]
        )

    shear_value_rows = [
        [str(point["span"]), money(float(point["local_x"])), money(float(point["x"])), money(float(point["y"]))]
        for point in shear_points
    ]
    moment_value_rows = [
        [str(point["span"]), money(float(point["local_x"])), money(float(point["x"])), money(float(point["y"]))]
        for point in moment_points
    ]
    summary_rows = [
        ["Maximum absolute shear", max_shear["span"], money(max_shear["x"]), money(max_shear["value"])],
        ["Maximum absolute bending moment", max_moment["span"], money(max_moment["x"]), money(max_moment["value"])],
        ["Maximum support reaction", max(support_reactions.items(), key=lambda item: abs(item[1]))[0], "Support", money(max(support_reactions.values(), key=abs))] if supports else [],
    ]
    summary_rows = [row for row in summary_rows if row]

    return {
        "reaction_rows": reaction_rows,
        "support_rows": support_rows,
        "reaction_calc_rows": reaction_calc_rows,
        "support_reaction_calc_rows": support_reaction_calc_rows,
        "shear_calc_rows": shear_calc_rows,
        "bending_calc_rows": bending_calc_rows,
        "equilibrium_rows": equilibrium_rows,
        "extrema_rows": extrema_rows,
        "shear_value_rows": shear_value_rows,
        "moment_value_rows": moment_value_rows,
        "summary_rows": summary_rows,
        "diagrams": {
            "shear": shear_points,
            "moment": moment_points,
            "supports": support_positions,
        },
        "beam": {
            "spans": span_infos,
            "supports": support_positions,
            "support_reactions": support_reactions,
        },
    }


APP_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hardy Cross Moment Distribution</title>
  <script>
    window.MathJax = {
      tex: { inlineMath: [['\\(', '\\)'], ['$', '$']] },
      svg: { fontCache: 'global' }
    };
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f6f8;
      --panel: #ffffff;
      --line: #d9e0e7;
      --text: #1b2430;
      --muted: #667085;
      --accent: #1264a3;
      --accent-dark: #0d4d7d;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14px;
    }
    header {
      padding: 16px 22px;
      background: #16202a;
      color: #fff;
    }
    h1 {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0;
    }
    main {
      display: grid;
      grid-template-columns: minmax(340px, 430px) minmax(0, 1fr);
      gap: 14px;
      padding: 14px;
      height: calc(100vh - 56px);
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .inputs {
      display: flex;
      flex-direction: column;
      min-height: 0;
    }
    .section {
      padding: 14px;
      border-bottom: 1px solid var(--line);
    }
    .section:last-child { border-bottom: 0; }
    h2 {
      margin: 0 0 10px;
      font-size: 15px;
    }
    label {
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }
    input[type="number"], input[type="text"] {
      width: 100%;
      border: 1px solid #cfd7df;
      border-radius: 6px;
      padding: 8px;
      font: inherit;
      background: #fff;
    }
    input[type="checkbox"] {
      width: 16px;
      height: 16px;
      vertical-align: middle;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }
    .span-list {
      overflow: auto;
      padding: 12px 14px;
      min-height: 0;
      flex: 1;
    }
    .span-row {
      display: grid;
      grid-template-columns: 52px 1fr 1fr;
      gap: 8px;
      align-items: end;
      margin-bottom: 10px;
    }
    .span-row .points { grid-column: 2 / 4; }
    .span-name {
      align-self: center;
      font-weight: 700;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      padding: 14px;
      border-top: 1px solid var(--line);
    }
    button {
      border: 0;
      border-radius: 6px;
      padding: 10px 12px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }
    .primary {
      background: var(--accent);
      color: #fff;
    }
    .primary:hover { background: var(--accent-dark); }
    .secondary {
      background: #e8edf2;
      color: #1b2430;
    }
    .status {
      grid-column: 1 / 3;
      min-height: 20px;
      color: var(--muted);
    }
    .status.error { color: var(--danger); }
    .tabs {
      display: flex;
      gap: 6px;
      padding: 10px 10px 0;
      border-bottom: 1px solid var(--line);
      background: #fbfcfd;
    }
    .tab {
      background: transparent;
      color: var(--muted);
      border-radius: 6px 6px 0 0;
      padding: 9px 10px;
    }
    .tab.active {
      color: var(--text);
      background: #fff;
      border: 1px solid var(--line);
      border-bottom-color: #fff;
      margin-bottom: -1px;
    }
    .table-wrap {
      overflow: auto;
      height: calc(100vh - 126px);
      padding: 12px;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      min-width: 720px;
      background: #fff;
    }
    th, td {
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      white-space: nowrap;
      vertical-align: top;
    }
    th {
      position: sticky;
      top: 0;
      background: #edf2f7;
      z-index: 1;
    }
    .formula {
      margin: 0 0 10px;
      color: var(--muted);
      line-height: 1.4;
    }
    .math-fallback {
      font-family: "Cambria Math", "Times New Roman", serif;
      font-style: italic;
      white-space: nowrap;
    }
    .stack {
      display: grid;
      gap: 14px;
    }
    .subheading {
      margin: 6px 0 8px;
      font-size: 14px;
      font-weight: 700;
    }
    .diagram {
      width: 100%;
      min-width: 720px;
      height: 300px;
      border: 1px solid var(--line);
      background: #fff;
    }
    .diagram path.curve {
      fill: none;
      stroke-width: 2.5;
    }
    .diagram .axis {
      stroke: #344054;
      stroke-width: 1;
    }
    .diagram .grid-line {
      stroke: #e5eaf0;
      stroke-width: 1;
    }
    .diagram text {
      font-size: 11px;
      fill: #344054;
    }
    tr.check-fail td {
      background: #fff1f0;
      color: #b42318;
      font-weight: 700;
    }
    tr.check-pass td {
      background: #f0fdf4;
    }
    @media (max-width: 860px) {
      main {
        grid-template-columns: 1fr;
        height: auto;
      }
      .table-wrap { height: 58vh; }
    }
  </style>
</head>
<body>
  <header><h1>Hardy Cross Moment Distribution</h1></header>
  <main>
    <section class="panel inputs">
      <div class="section">
        <h2>Beam Input</h2>
        <div class="grid">
          <div>
            <label for="supportCount">Number of supports</label>
            <input id="supportCount" type="number" min="2" max="30" value="3">
          </div>
          <div>
            <label for="maxCycles">Maximum cycles</label>
            <input id="maxCycles" type="number" min="1" value="50">
          </div>
          <div>
            <label for="tolerance">Tolerance</label>
            <input id="tolerance" type="text" value="0.0001">
          </div>
          <div>
            <label>&nbsp;</label>
            <label><input id="exteriorFixed" type="checkbox"> Exterior supports fixed</label>
            <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">Leave unchecked if exterior supports are pins/rollers (not strictly fixed).</div>
          </div>
        </div>
      </div>
      <div class="span-list">
        <h2>Spans</h2>
        <p class="formula">Point loads use <strong>P@a</strong>, where <strong>a</strong> is the distance from the left support. Separate multiple point loads with semicolons.</p>
        <div id="spans"></div>
      </div>
      <div class="actions">
        <button class="primary" id="calculate">Calculate</button>
        <button class="secondary" id="clear">Clear Outputs</button>
        <div id="status" class="status">Enter span data, then calculate.</div>
      </div>
    </section>
    <section class="panel">
      <nav class="tabs" id="tabs"></nav>
      <div class="table-wrap" id="output"></div>
    </section>
  </main>
  <script>
    const supportCount = document.getElementById('supportCount');
    const spansEl = document.getElementById('spans');
    const statusEl = document.getElementById('status');
    const tabsEl = document.getElementById('tabs');
    const outputEl = document.getElementById('output');
    let currentResults = null;
    let activeTab = 'distribution';

    const tabLabels = {
      distribution: 'Distribution Factors',
      fem: 'Fixed-End Moment Calculations',
      moment: 'Moment Distribution',
      reactions: 'Reactions',
      diagrams: 'SFD / BMD',
      support: 'Final Support Moments'
    };

    function supportName(index) {
      const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
      return index < alphabet.length ? alphabet[index] : `S${index + 1}`;
    }

    function rebuildSpans() {
      const count = Number(supportCount.value);
      const old = new Map([...spansEl.querySelectorAll('.span-row')].map(row => [row.dataset.span, {
        length: row.querySelector('.length').value,
        udl: row.querySelector('.udl').value,
        pointLoads: row.querySelector('.point-loads').value
      }]));
      spansEl.innerHTML = '';
      if (!Number.isFinite(count) || count < 2) return;
      for (let i = 0; i < count - 1; i++) {
        const left = supportName(i);
        const right = supportName(i + 1);
        const name = `${left}${right}`;
        const previous = old.get(name) || { length: '', udl: '0', pointLoads: '' };
        const row = document.createElement('div');
        row.className = 'span-row';
        row.dataset.span = name;
        row.innerHTML = `
          <div class="span-name">${name}</div>
          <div>
            <label>Length L</label>
            <input class="length" type="text" value="${escapeAttr(previous.length)}">
          </div>
          <div>
            <label>UDL w</label>
            <input class="udl" type="text" value="${escapeAttr(previous.udl)}">
          </div>
          <div class="points">
            <label>Point loads</label>
            <input class="point-loads" type="text" placeholder="12@2; 8@4.5" value="${escapeAttr(previous.pointLoads)}">
          </div>
        `;
        spansEl.appendChild(row);
      }
    }

    function escapeAttr(value) {
      return String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
    }

    function collectPayload() {
      const spans = [...spansEl.querySelectorAll('.span-row')].map(row => ({
        length: row.querySelector('.length').value,
        udl: row.querySelector('.udl').value,
        point_loads: row.querySelector('.point-loads').value
      }));
      return {
        support_count: supportCount.value,
        exterior_fixed: document.getElementById('exteriorFixed').checked,
        tolerance: document.getElementById('tolerance').value,
        max_cycles: document.getElementById('maxCycles').value,
        spans
      };
    }

    async function calculate() {
      setStatus('Calculating...', false);
      const response = await fetch('/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(collectPayload())
      });
      const data = await response.json();
      if (!response.ok) {
        setStatus(data.error || 'Calculation failed.', true);
        return;
      }
      currentResults = data;
      setStatus(data.status, false);
      renderTabs();
      renderActiveTable();
      typesetMath();
    }

    function setStatus(message, isError) {
      statusEl.textContent = message;
      statusEl.classList.toggle('error', Boolean(isError));
    }

    function renderTabs() {
      tabsEl.innerHTML = '';
      Object.entries(tabLabels).forEach(([key, label]) => {
        const button = document.createElement('button');
        button.className = `tab ${key === activeTab ? 'active' : ''}`;
        button.textContent = label;
        button.addEventListener('click', () => {
          activeTab = key;
          renderTabs();
          renderActiveTable();
        });
        tabsEl.appendChild(button);
      });
    }

    function renderActiveTable() {
      if (!currentResults) {
        outputEl.innerHTML = '<p class="formula">Results will appear here after calculation.</p>';
        return;
      }
      const table = currentResults.tables[activeTab];
      if (activeTab === 'diagrams') {
        outputEl.innerHTML = renderDiagrams();
        typesetMath();
        return;
      }
      if (activeTab === 'reactions') {
        outputEl.innerHTML = `
          <div class="stack">
            <div>
              <h2 class="subheading">Beam, Loads, and Support Reactions</h2>
              <p class="formula">The reaction forces shown below are the same forces used to close the SFD jumps at the supports.</p>
              ${drawBeamSketch()}
            </div>
            <div>
              <h2 class="subheading">Span Reaction Force Calculations</h2>
              ${renderFbdCalculations()}
            </div>
            <div>
              <h2 class="subheading">Support Reaction Summation</h2>
              ${renderSupportReactionCalculations(currentResults.tables.support_reaction_calculations.rows)}
            </div>
            <div>
              <h2 class="subheading">Span-End Reactions</h2>
              ${buildTable(currentResults.tables.reactions.headers, currentResults.tables.reactions.rows)}
            </div>
            <div>
              <h2 class="subheading">Total Support Reactions</h2>
              ${buildTable(currentResults.tables.support_reactions.headers, currentResults.tables.support_reactions.rows)}
            </div>
            <div>
              <h2 class="subheading">Equilibrium Checks</h2>
              <p class="formula">A zero residual means the check is balanced. Nonzero residuals are shown in red.</p>
              ${buildTable(currentResults.tables.equilibrium_checks.headers, currentResults.tables.equilibrium_checks.rows)}
              <div style="font-size: 13px; color: var(--muted); margin-top: 8px;">
                <strong>Legend:</strong> \\(R_L\\) = Left Span Reaction, \\(R_R\\) = Right Span Reaction, \\(\\Sigma W\\) = Total downward force (UDL + Point Loads), \\(\\Sigma M_{joint}\\) = Sum of member-end moments at a joint.
              </div>
            </div>
          </div>
        `;
        typesetMath();
        return;
      }
      const note = activeTab === 'fem'
        ? '<p class="formula">Clockwise member-end moments are positive. \\(UDL: M_L=-wL^2/12, M_R=wL^2/12\\). Point load: \\(M_L=-Pab^2/L^2, M_R=Pa^2b/L^2\\), where \\(b=L-a\\).</p>'
        : activeTab === 'distribution'
        ? '<p class="formula">Relative stiffness remains \\(k=1/L\\), and \\(DF=k/\\Sigma k\\).</p>'
        : '';
      outputEl.innerHTML = note + buildTable(table.headers, table.rows);
      typesetMath();
    }

    function buildTable(headers, rows) {
      const head = headers.map(header => `<th>${formatCell(header)}</th>`).join('');
      const body = rows.map(row => `<tr class="${rowClass(row)}">${row.map(cell => `<td>${formatCell(cell)}</td>`).join('')}</tr>`).join('');
      return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
    }

    function rowClass(row) {
      const status = String(row[row.length - 1] || '').toLowerCase();
      if (status.includes('fixed-end')) return '';
      if (status.includes('unbalanced') || status.includes('residual')) return 'check-fail';
      if (status.includes('balanced')) return 'check-pass';
      return '';
    }

    function renderDiagrams() {
      return `
        <div class="stack">
          <div>
            <h2 class="subheading">Beam, Loads, and Support Reactions</h2>
            ${drawBeamSketch()}
          </div>
          <div>
            <h2 class="subheading">Maximum Values</h2>
            ${buildTable(currentResults.tables.extrema.headers, currentResults.tables.extrema.rows)}
            <div style="font-size: 13px; color: var(--text); margin-top: 10px; line-height: 1.5; background: #fff8e6; padding: 12px; border: 1px solid #ffd54f; border-radius: 6px;">
              <strong style="color: #b78103;">💡 Design Note:</strong><br>
              &bull; Use <strong>Maximum absolute shear</strong> for the shear design of the beam itself (sizing vertical stirrups/links).<br>
              &bull; Use <strong>Maximum support reaction</strong> for designing the supporting elements (sizing columns, walls, or checking bearing pressure).<br>
              &bull; <strong>"x from left support"</strong> is simply the distance (in meters) measured starting from the left end of that specific span.
            </div>
          </div>
          <div>
            <h2 class="subheading">Shear Force Diagram</h2>
            <p class="formula">\\(V(x)=R_L-wx-\\Sigma P_{a\\le x}\\)</p>
            ${drawDiagram(currentResults.diagrams.shear, currentResults.diagrams.supports, '#1264a3', 'SFD')}
          </div>
          <div>
            <h2 class="subheading">Bending Moment Diagram</h2>
            <p class="formula">Bending moment is calculated from the area under the shear force diagram: \\(M(x)=M_L+\\int_0^x V(s)\\,ds\\).</p>
            ${drawDiagram(currentResults.diagrams.moment, currentResults.diagrams.supports, '#b42318', 'BMD')}
          </div>
          <div>
            <h2 class="subheading">Shear Calculations</h2>
            ${buildTable(currentResults.tables.shear_calculations.headers, currentResults.tables.shear_calculations.rows)}
            <div style="font-size: 13px; color: var(--muted); margin-top: 8px;">
              <strong>Legend:</strong> \\(V(l)\\) = Internal Shear Force, \\(R_L\\) = Left Reaction, \\(w\\) = UDL, \\(l\\) = Distance from left support, \\(\\Sigma P\\) = Sum of point loads.
            </div>
          </div>
          <div>
            <h2 class="subheading">Bending Moment Calculations</h2>
            ${buildTable(currentResults.tables.bending_calculations.headers, currentResults.tables.bending_calculations.rows)}
            <div style="font-size: 13px; color: var(--muted); margin-top: 8px;">
              <strong>Note:</strong> The bending moment calculated here is the <em>internal</em> bending moment. For a simply supported (pinned/roller) end, the internal moment is naturally 0. At fixed supports or continuous interior supports, the internal moment matches the non-zero member-end moment (\\(M_L\\) or \\(M_R\\)) required for continuity.
            </div>
          </div>
          <div>
            <h2 class="subheading">Station Values</h2>
            ${buildTable(currentResults.tables.station_values.headers, currentResults.tables.station_values.rows)}
          </div>
        </div>
      `;
    }

    function drawBeamSketch() {
      const beam = currentResults.beam;
      if (!beam || !beam.spans || beam.spans.length === 0) return '<p class="formula">No beam data.</p>';
      const width = 980;
      const height = 300;
      const pad = { left: 58, right: 28, top: 28, bottom: 52 };
      const minX = 0;
      const maxX = Math.max(...beam.supports.map(support => support.x));
      const beamY = 150;
      const xScale = x => pad.left + ((x - minX) / Math.max(1e-9, maxX - minX)) * (width - pad.left - pad.right);

      const spanLines = beam.spans.map(span => {
        const x1 = xScale(span.start);
        const x2 = xScale(span.end);
        const mid = (x1 + x2) / 2;
        const udl = Number(span.udl);
        const udlMarkup = udl > 0 ? drawUdl(x1, x2, beamY - 72, beamY - 18, `${udl.toFixed(2)} / length`) : '';
        const points = (span.point_loads || []).map(point => {
          const x = xScale(span.start + Number(point.distance));
          return drawArrow(x, beamY - 78, x, beamY - 16, '#b42318', `${Number(point.load).toFixed(2)}`);
        }).join('');
        return `
          <line x1="${x1}" y1="${beamY}" x2="${x2}" y2="${beamY}" stroke="#1b2430" stroke-width="4"></line>
          <text x="${mid - 18}" y="${beamY + 34}">${escapeHtml(span.name)}</text>
          <text x="${mid - 28}" y="${beamY + 52}">L=${Number(span.length).toFixed(2)}</text>
          ${udlMarkup}
          ${points}
        `;
      }).join('');

      const supportMarks = beam.supports.map(support => {
        const x = xScale(support.x);
        const reaction = Number(beam.support_reactions[support.name] || 0);
        const reactionArrow = reaction >= 0
          ? drawArrow(x, beamY + 72, x, beamY + 18, '#1264a3', `${reaction.toFixed(2)}`)
          : drawArrow(x, beamY + 18, x, beamY + 72, '#1264a3', `${reaction.toFixed(2)}`);
        return `
          <polygon points="${x - 12},${beamY + 24} ${x + 12},${beamY + 24} ${x},${beamY + 2}" fill="#e8edf2" stroke="#344054"></polygon>
          <text x="${x - 5}" y="${beamY + 92}">${escapeHtml(support.name)}</text>
          ${reactionArrow}
        `;
      }).join('');

      return `
        <svg class="diagram" viewBox="0 0 ${width} ${height}" role="img" aria-label="Beam loads and reactions">
          <defs>
            <marker id="arrow-blue" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#1264a3"></path>
            </marker>
            <marker id="arrow-red" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto">
              <path d="M0,0 L8,4 L0,8 Z" fill="#b42318"></path>
            </marker>
          </defs>
          ${spanLines}
          ${supportMarks}
          <text x="${pad.left}" y="18">Beam, loads, and final support reactions</text>
        </svg>
      `;
    }

    function drawUdl(x1, x2, yTop, yBottom, label) {
      const count = Math.max(3, Math.min(10, Math.floor((x2 - x1) / 55)));
      const arrows = [];
      for (let index = 0; index < count; index += 1) {
        const x = x1 + ((index + 0.5) / count) * (x2 - x1);
        arrows.push(drawArrow(x, yTop, x, yBottom, '#b42318', ''));
      }
      return `
        <line x1="${x1 + 8}" y1="${yTop}" x2="${x2 - 8}" y2="${yTop}" stroke="#b42318" stroke-width="2"></line>
        ${arrows.join('')}
        <text x="${(x1 + x2) / 2 - 26}" y="${yTop - 8}">${escapeHtml(label)}</text>
      `;
    }

    function drawArrow(x1, y1, x2, y2, color, label) {
      const marker = color === '#1264a3' ? 'arrow-blue' : 'arrow-red';
      const textY = y1 < y2 ? y1 - 6 : y1 + 16;
      return `
        <line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="2.5" marker-end="url(#${marker})"></line>
        ${label ? `<text x="${x1 + 5}" y="${textY}">${escapeHtml(label)}</text>` : ''}
      `;
    }

    function drawDiagram(points, supports, color, label) {
      if (!points || points.length === 0) return '<p class="formula">No diagram data.</p>';
      const width = 980;
      const height = 300;
      const pad = { left: 56, right: 20, top: 22, bottom: 42 };
      const xs = points.map(point => point.x);
      const ys = points.map(point => point.y);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const maxAbsY = Math.max(1, ...ys.map(value => Math.abs(value)));
      const xScale = x => pad.left + ((x - minX) / Math.max(1e-9, maxX - minX)) * (width - pad.left - pad.right);
      const yScale = y => pad.top + ((maxAbsY - y) / (2 * maxAbsY)) * (height - pad.top - pad.bottom);
      const zeroY = yScale(0);
      const path = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${xScale(point.x).toFixed(2)} ${yScale(point.y).toFixed(2)}`).join(' ');
      const supportMarks = supports.map(support => {
        const x = xScale(support.x);
        return `<line class="grid-line" x1="${x}" y1="${pad.top}" x2="${x}" y2="${height - pad.bottom}"></line><text x="${x - 4}" y="${height - 18}">${escapeHtml(support.name)}</text>`;
      }).join('');
      const labelPoints = selectDiagramLabels(points, maxAbsY);
      const labels = labelPoints
        .map((point, index) => {
          const x = xScale(point.x) + 4;
          // Offset zero labels so they don't overlap with small values like 3.39
          const isZero = Math.abs(point.y) < 1e-4;
          const yOffset = isZero ? 14 : (index % 2 === 0 ? -8 : 16);
          const y = yScale(point.y) + yOffset;
          return `<text x="${x}" y="${y}">${Number(point.y).toFixed(2)}</text>`;
        })
        .join('');
      return `
        <svg class="diagram" viewBox="0 0 ${width} ${height}" role="img" aria-label="${label}">
          <line class="axis" x1="${pad.left}" y1="${zeroY}" x2="${width - pad.right}" y2="${zeroY}"></line>
          <line class="axis" x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}"></line>
          ${supportMarks}
          <path class="curve" d="${path}" stroke="${color}"></path>
          ${labels}
          <text x="${pad.left}" y="15">${label}</text>
        </svg>
      `;
    }

    function selectDiagramLabels(points, maxAbsY) {
      const selected = [];
      const seen = new Set();
      points.forEach((point, index) => {
        const isSupport = currentResults.diagrams.supports.some(support => Math.abs(support.x - point.x) < 1e-6);
        const isExtreme = Math.abs(Math.abs(point.y) - maxAbsY) < 1e-6;
        const isZero = Math.abs(point.y) < 1e-6;
        const isKey = Boolean(point.key);
        if (index === 0 || index === points.length - 1 || isSupport || isExtreme || isZero || isKey) {
          const key = `${point.x.toFixed(4)}:${point.y.toFixed(4)}`;
          if (!seen.has(key)) {
            seen.add(key);
            selected.push(point);
          }
        }
      });
      return selected;
    }

    function renderFbdCalculations() {
      const spans = currentResults.beam?.spans;
      if (!spans || spans.length === 0) return '<p class="formula">No data.</p>';
      
      return spans.map(span => {
        const mlStr = Number(span.ml).toFixed(3);
        const mrStr = Number(span.mr).toFixed(3);
        const mlNum = Number(span.ml);
        const mrNum = Number(span.mr);
        
        // Define SVG dimensions
        const w = 400, h = 180;
        const pad = 60;
        const beamY = 100;
        
        // Helper to draw curved moment arrows
        // If moment is positive (clockwise), draw clockwise arrow. If negative, draw CCW.
        const drawMoment = (x, isLeft, value) => {
          if (Math.abs(value) < 1e-4) return '';
          const isCw = value > 0;
          // SVG arc: A rx ry x-axis-rotation large-arc-flag sweep-flag x y
          // Left side: start from top, go right and down.
          const radius = 16;
          const startX = isLeft ? x - 10 : x - 10;
          const sweep = isCw ? 1 : 0;
          const endX = isLeft ? x + 10 : x + 10;
          const color = '#dfbe00'; // Match video yellow highlight
          const path = isCw
             ? `M ${startX} ${beamY - 5} A ${radius} ${radius} 0 1 1 ${endX} ${beamY - 5}`
             : `M ${endX} ${beamY - 5} A ${radius} ${radius} 0 1 0 ${startX} ${beamY - 5}`;
             
          const arrowHead = isCw
             ? `<polygon points="${endX-4},${beamY - 12} ${endX+6},${beamY - 5} ${endX-6},${beamY}" fill="${color}"/>`
             : `<polygon points="${startX+4},${beamY - 12} ${startX-6},${beamY - 5} ${startX+6},${beamY}" fill="${color}"/>`;
             
          return `
            <path d="${path}" fill="none" stroke="${color}" stroke-width="3" />
            ${arrowHead}
            <rect x="${x - 30}" y="${beamY - 45}" width="60" height="20" fill="#ffeb3b" opacity="0.4"/>
            <text x="${x}" y="${beamY - 32}" text-anchor="middle" font-weight="bold" font-size="12">${Math.abs(value).toFixed(3)} kN&middot;m</text>
          `;
        };

        const loadMoment = Number(span.load_moment);
        const totalLoad = Number(span.total_load);
        const rl = Number(span.left_reaction);
        const rr = Number(span.right_reaction);
        const leftSup = span.left;
        const rightSup = span.right;
        
        let pointLoadsHtml = '';
        if (span.point_loads && span.point_loads.length > 0) {
            pointLoadsHtml = span.point_loads.map(p => {
               const px = pad + (p.distance / span.length) * (w - 2 * pad);
               return `<line x1="${px}" y1="${beamY - 40}" x2="${px}" y2="${beamY - 5}" stroke="#222" stroke-width="2" marker-end="url(#arrow-red)"/>
                       <text x="${px}" y="${beamY - 45}" text-anchor="middle">${p.load} kN</text>`;
            }).join('');
        }
        
        let udlHtml = '';
        if (span.udl > 0) {
            udlHtml = `<rect x="${pad}" y="${beamY - 12}" width="${w - 2 * pad}" height="12" fill="#4caf50" opacity="0.5"/>
                       <text x="${w/2}" y="${beamY - 18}" text-anchor="middle" font-size="12" fill="#1b5e20">${span.udl} kN/m</text>`;
        }

        const fbdSvg = `
          <svg viewBox="0 0 ${w} ${h}" style="max-width: 400px; background: #fff; border: 1px solid #e5eaf0; border-radius: 4px; margin-bottom: 12px; font-family: 'Comic Sans MS', cursive, sans-serif;">
            <!-- Beam -->
            <line x1="${pad}" y1="${beamY}" x2="${w - pad}" y2="${beamY}" stroke="#333" stroke-width="3" />
            
            <!-- Nodes -->
            <text x="${pad - 15}" y="${beamY + 5}" font-size="14" font-weight="bold">${leftSup}</text>
            <text x="${w - pad + 15}" y="${beamY + 5}" font-size="14" font-weight="bold">${rightSup}</text>
            
            <!-- Moments -->
            ${drawMoment(pad, true, mlNum)}
            ${drawMoment(w - pad, false, mrNum)}
            
            <!-- Loads -->
            ${udlHtml}
            ${pointLoadsHtml}
            
            <!-- Reactions -->
            <line x1="${pad}" y1="${beamY + 30}" x2="${pad}" y2="${beamY + 5}" stroke="#222" stroke-width="2" marker-end="url(#arrow-blue)"/>
            <rect x="${pad - 15}" y="${beamY + 35}" width="30" height="20" fill="#ffeb3b" opacity="0.4"/>
            <text x="${pad}" y="${beamY + 50}" text-anchor="middle" font-weight="bold" font-size="13">R_${leftSup}</text>
            
            <line x1="${w - pad}" y1="${beamY + 30}" x2="${w - pad}" y2="${beamY + 5}" stroke="#222" stroke-width="2" marker-end="url(#arrow-blue)"/>
            <rect x="${w - pad - 15}" y="${beamY + 35}" width="30" height="20" fill="#00bcd4" opacity="0.4"/>
            <text x="${w - pad}" y="${beamY + 50}" text-anchor="middle" font-weight="bold" font-size="13">R_${rightSup}</text>
            
            <!-- Dimension line -->
            <line x1="${pad}" y1="${beamY + 70}" x2="${w - pad}" y2="${beamY + 70}" stroke="#777" stroke-width="1" />
            <line x1="${pad}" y1="${beamY + 65}" x2="${pad}" y2="${beamY + 75}" stroke="#777" stroke-width="1" />
            <line x1="${w - pad}" y1="${beamY + 65}" x2="${w - pad}" y2="${beamY + 75}" stroke="#777" stroke-width="1" />
            <rect x="${w/2 - 20}" y="${beamY + 60}" width="40" height="15" fill="#ffeb3b" opacity="0.4"/>
            <text x="${w/2}" y="${beamY + 74}" text-anchor="middle" font-size="12">${span.length} m</text>
          </svg>
        `;

        const momentEq = `\\( \\Sigma M_{@${leftSup}} = 0 \\quad \\circlearrowright + \\)`;
        
        let momentExpression = `${mlStr} \\text{ (M_L)} `;
        if (loadMoment !== 0) {
             let loadFormulas = [];
             if (span.udl > 0) {
                 loadFormulas.push(`(${span.udl} \\times ${span.length} \\times \\frac{${span.length}}{2})`);
             }
             if (span.point_loads && span.point_loads.length > 0) {
                 span.point_loads.forEach(p => {
                     loadFormulas.push(`(${p.load} \\times ${p.distance})`);
                 });
             }
             momentExpression += `+ [${loadFormulas.join(' + ')}] \\text{ (Loads)} `;
        }
        momentExpression += `+ ${mrStr} \\text{ (M_R)} - R_${rightSup} \\times ${span.length} = 0`;

        const forceEq = `\\( \\Sigma F_y = 0 \\quad \\uparrow + \\)`;
        const forceExpression = `R_${leftSup} - ${totalLoad.toFixed(3)} \\text{ (Loads)} + ${rr.toFixed(3)} \\text{ (R_${rightSup})} = 0`;

        return `
        <div style="margin-bottom: 24px; padding: 16px; background: #fafafa; border: 1px solid var(--line); border-radius: 8px;">
          <h3 style="margin: 0 0 12px; font-size: 16px; font-family: 'Comic Sans MS', cursive, sans-serif;">FBD of segment ${span.name}</h3>
          ${fbdSvg}
          <div style="display: grid; gap: 12px; font-size: 15px;">
             <div>
                <div>${momentEq}</div>
                <div style="margin-top: 8px;">\\( \\Rightarrow ${momentExpression} \\)</div>
                <div style="margin-top: 8px;">\\( \\Rightarrow R_${rightSup} = \\mathbf{${rr.toFixed(2)}\\text{ kN}} \\)</div>
             </div>
             <hr style="border: 0; border-top: 1px dashed #ccc; width: 100%; margin: 4px 0;">
             <div>
                <div>${forceEq}</div>
                <div style="margin-top: 8px;">\\( \\Rightarrow ${forceExpression} \\)</div>
                <div style="margin-top: 8px;">\\( \\Rightarrow R_${leftSup} = \\mathbf{${rl.toFixed(2)}\\text{ kN}} \\)</div>
             </div>
          </div>
        </div>`;
      }).join('');
    }

    function renderSupportReactionCalculations(rows) {
      if (!rows || rows.length === 0) return '<p class="formula">No data.</p>';
      let html = '<div style="display: grid; gap: 10px;">';
      for (const row of rows) {
        html += `<div style="padding: 10px; background: #fff; border: 1px solid var(--line); border-radius: 6px;">
          <strong style="display: inline-block; width: 80px; font-size: 14px;">Support ${escapeHtml(row[0])}</strong> 
          <span style="color: var(--muted);">${escapeHtml(row[2])} = </span> <strong>${escapeHtml(row[3])}</strong>
          <div style="font-size: 13px; color: var(--muted); margin-top: 6px;">Contributions from adjacent spans: ${escapeHtml(row[1])}</div>
        </div>`;
      }
      html += '</div>';
      return html;
    }

    function typesetMath() {
      if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([outputEl]).catch(() => {});
      } else {
        setTimeout(() => {
          if (!(window.MathJax && window.MathJax.typesetPromise)) {
            applyMathFallback(outputEl);
          }
        }, 800);
      }
    }

    function escapeHtml(value) {
      return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
    }

    function formatCell(value) {
      return escapeHtml(value);
    }

    function applyMathFallback(root) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      const textNodes = [];
      while (walker.nextNode()) {
        if (walker.currentNode.nodeValue.includes('\\(')) textNodes.push(walker.currentNode);
      }
      textNodes.forEach(node => {
        const wrapper = document.createElement('span');
        wrapper.innerHTML = escapeHtml(node.nodeValue).replace(/\\\((.*?)\\\)/g, (_match, formula) => `<span class="math-fallback">${latexFallback(formula)}</span>`);
        node.parentNode.replaceChild(wrapper, node);
      });
    }

    function latexFallback(formula) {
      return escapeHtml(formula)
        .replaceAll('\\Sigma', 'Σ')
        .replaceAll('\\sum', 'Σ')
        .replaceAll('\\int', '∫')
        .replaceAll('\\le', '≤')
        .replaceAll('\\,', ' ')
        .replaceAll('_L', '<sub>L</sub>')
        .replaceAll('_R', '<sub>R</sub>')
        .replaceAll('_left', '<sub>left</sub>')
        .replaceAll('_right', '<sub>right</sub>')
        .replaceAll('^2', '<sup>2</sup>');
    }

    document.getElementById('calculate').addEventListener('click', () => {
      calculate().catch(error => setStatus(error.message, true));
    });
    document.getElementById('clear').addEventListener('click', () => {
      currentResults = null;
      renderActiveTable();
      setStatus('Outputs cleared.', false);
    });
    supportCount.addEventListener('change', rebuildSpans);
    supportCount.addEventListener('input', rebuildSpans);
    rebuildSpans();
    renderTabs();
    renderActiveTable();
  </script>
</body>
</html>
"""


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
                "headers": ["Span", "Load", "End", "Formula", "Substitution", "Moment"],
                "rows": [row for span in spans for row in span.fixed_end_detail_rows()],
            },
            "moment": {"headers": md_headers, "rows": md_rows},
            "reactions": {
                "headers": ["Support", "Span", "Component", "Reaction"],
                "rows": analysis["reaction_rows"],
            },
            "support_reactions": {
                "headers": ["Support", "Total vertical reaction"],
                "rows": analysis["support_rows"],
            },
            "support_reaction_calculations": {
                "headers": ["Support", "Span-end reaction parts", "Summation", "Total reaction"],
                "rows": analysis["support_reaction_calc_rows"],
            },
            "reaction_calculations": {
                "headers": ["Span", "Calculation", "Formula", "Substitution", "Value"],
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
            "station_values": {
                "headers": ["Span", "l from left support (m)", "Shear V", "Bending moment M"],
                "rows": analysis["extrema_rows"],
            },
            "shear_values": {
                "headers": ["Span", "Local l", "Global l", "Shear V"],
                "rows": analysis["shear_value_rows"],
            },
            "moment_values": {
                "headers": ["Span", "Local x", "Global x", "Bending moment M"],
                "rows": analysis["moment_value_rows"],
            },
            "extrema": {
                "headers": ["Result", "Span", "x from left support", "Value"],
                "rows": analysis["summary_rows"],
            },
            "support": {
                "headers": ["Support", "Member-end moments", "Algebraic joint sum"],
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
        self.wfile.write(APP_HTML.encode("utf-8"))

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Hardy Cross moment distribution browser GUI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="Preferred port. Default: 8000")
    parser.add_argument(
        "--port-attempts",
        type=int,
        default=10,
        help="Number of sequential ports to try if the preferred port is busy. Default: 10",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server, port = create_server(args.host, args.port, args.port_attempts)

    print("Hardy Cross Moment Distribution GUI")
    print(f"Open http://{args.host}:{port} in your browser.")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
