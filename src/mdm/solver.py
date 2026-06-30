from __future__ import annotations
import math
from typing import Dict, List, Tuple

from .core import Span, money, fmt

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
    zero_shear_calcs: List[Dict[str, object]] = []
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
        for l_val in station_candidates:
            shear = shear_at(span, left_reaction, l_val, after_point_loads=True)
            moment = moment_at(span, final_moments, left_reaction, l_val)
            if abs(moment) > abs(max_moment["value"]):
                max_moment = {"span": span.name, "x": l_val, "value": moment}
            extrema_rows.append([span.name, money(l_val), money(shear), money(moment)])
            
            if 0.0 < l_val < span.length and not any(math.isclose(l_val, pt[1], abs_tol=1e-6) for pt in span.point_loads):
                if math.isclose(shear_at(span, left_reaction, l_val), 0.0, abs_tol=1e-6) and span.udl > 0:
                    start_val = max([0.0] + [pt[1] for pt in span.point_loads if pt[1] < l_val])
                    shear_start = shear_at(span, left_reaction, start_val, after_point_loads=True)
                    zero_shear_calcs.append({
                        "span": span.name,
                        "start": start_val,
                        "v_start": shear_start,
                        "udl": span.udl,
                        "root": l_val
                    })

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
            "zero_shear_calcs": zero_shear_calcs,
        },
    }
