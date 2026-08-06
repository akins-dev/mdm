from __future__ import annotations
import math
from typing import Dict, List, Tuple, Any

from ..models.beam import Span, money, fmt


def build_distribution_rows(
    spans: List[Span],
    supports: List[str],
    fixed_supports: set[str],
) -> Tuple[List[List[str]], Dict[str, float], Dict[str, List[str]], Dict[str, str]]:
    joint_ends: Dict[str, List[str]] = {support: [] for support in supports}
    end_to_span: Dict[str, Span] = {}
    opposite: Dict[str, str] = {}

    for span in spans:
        if span.left in joint_ends:
            joint_ends[span.left].append(span.left_end)
        if span.right in joint_ends:
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
    joint_counts = {}
    for r in rows:
        joint_counts[r[0]] = joint_counts.get(r[0], 0) + 1
        
    seen_joints = set()
    
    for joint, span_name, end, stiffness, joint_sum, df in rows:
        span = next(span for span in spans if span.name == span_name)
        
        if joint not in seen_joints:
            count = joint_counts[joint]
            joint_val = {"value": joint, "rowspan": count}
            sum_val = {"value": joint_sum, "rowspan": count}
            seen_joints.add(joint)
        else:
            joint_val = None
            sum_val = None
            
        standard_rows.append(
            [
                joint_val,
                end,
                "\\(0\\)" if span.stiffness == 0.0 else f"\\(1/{fmt(span.length)} = {stiffness}\\)",
                sum_val,
                df,
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
        ["Joints"] + [end_to_joint[end] for end in end_labels if end in end_to_joint],
        ["Members"] + [end for end in end_labels if end in end_to_joint],
        ["DF"] + [money(distribution_factors[end]) for end in end_labels if end in end_to_joint],
        ["FEM"] + [money(moments[end]) for end in end_labels if end in end_to_joint],
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

        rows.append([f"Distribution cycle {cycle}"] + [money(balance_row[end]) for end in end_labels if end in end_to_joint])
        rows.append([f"Carry over cycle {cycle}"] + [money(carry_row[end]) for end in end_labels if end in end_to_joint])

        max_unbalanced = max(
            [abs(sum(moments[end] for end in joint_ends[joint])) for joint in supports if joint not in fixed_supports] or [0.0]
        )
        if max_unbalanced <= tolerance:
            break

    rows.append(["End Moment"] + [money(moments[end]) for end in end_labels if end in end_to_joint])
    return rows[0], rows[1:], moments, cycles_used


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
    return sum(w * (b - a) for w, a, b in getattr(span, 'udls', [])) + sum(load for load, _distance in getattr(span, 'point_loads', []))


def load_moment_about_left(span: Span) -> float:
    udl_moment = sum(w * (b - a) * (a + b) / 2.0 for w, a, b in getattr(span, 'udls', []))
    return udl_moment + sum(load * distance for load, distance in getattr(span, 'point_loads', []))


def span_reactions(span: Span, final_moments: Dict[str, float]) -> Tuple[float, float]:
    total_load = total_span_load(span)
    moment_about_left = load_moment_about_left(span)
    left_moment = final_moments.get(span.left_end, 0.0)
    right_moment = final_moments.get(span.right_end, 0.0)
    right_reaction = (moment_about_left + left_moment + right_moment) / span.length
    left_reaction = total_load - right_reaction
    return left_reaction, right_reaction


def shear_at(span: Span, left_reaction: float, x: float, after_point_loads: bool = True) -> float:
    shear = left_reaction
    for w, a, b in getattr(span, 'udls', []):
        if x <= a:
            pass
        elif x <= b:
            shear -= w * (x - a)
        else:
            shear -= w * (b - a)
    for load, distance in getattr(span, 'point_loads', []):
        if distance < x or (after_point_loads and math.isclose(distance, x, abs_tol=1e-9)):
            shear -= load
    return shear


def moment_at(span: Span, final_moments: Dict[str, float], left_reaction: float, x: float) -> float:
    moment = final_moments.get(span.left_end, 0.0) + left_reaction * x
    for w, a, b in getattr(span, 'udls', []):
        if x <= a:
            pass
        elif x <= b:
            moment -= w * (x - a)**2 / 2.0
        else:
            moment -= w * (b - a) * (x - (a + b) / 2.0)
    for load, distance in getattr(span, 'point_loads', []):
        if x >= distance:
            moment -= load * (x - distance)
    return moment


def span_station_candidates(span: Span, final_moments: Dict[str, float], left_reaction: float) -> List[float]:
    candidates = {0.0, span.length}
    for _load, distance in getattr(span, 'point_loads', []):
        candidates.add(distance)
    for _w, a, b in getattr(span, 'udls', []):
        if 0.0 < a < span.length:
            candidates.add(a)
        if 0.0 < b < span.length:
            candidates.add(b)

    breakpoint_set = set()
    for _load, distance in getattr(span, 'point_loads', []):
        if 0.0 < distance < span.length:
            breakpoint_set.add(distance)
    for _w, a, b in getattr(span, 'udls', []):
        if 0.0 < a < span.length:
            breakpoint_set.add(a)
        if 0.0 < b < span.length:
            breakpoint_set.add(b)
    breakpoints = [0.0] + sorted(breakpoint_set) + [span.length]

    for seg_start, seg_end in zip(breakpoints, breakpoints[1:]):
        v_start = shear_at(span, left_reaction, seg_start, after_point_loads=True)
        v_end = shear_at(span, left_reaction, seg_end, after_point_loads=False)
        active_w = 0.0
        for w, a, b in getattr(span, 'udls', []):
            mid = (seg_start + seg_end) / 2.0
            if a <= mid <= b:
                active_w += w
        if active_w > 0 and v_start * v_end <= 0 and not math.isclose(v_start, 0.0, abs_tol=1e-9):
            root = seg_start + v_start / active_w
            if seg_start < root < seg_end and 0.0 <= root <= span.length:
                candidates.add(root)
        elif active_w == 0 and v_start * v_end < 0:
            pass

    return sorted(candidates)


def diagram_points(span: Span, final_moments: Dict[str, float], left_reaction: float, global_start: float) -> Tuple[List[Dict[str, object]], List[Dict[str, object]]]:
    x_values = {0.0, span.length}
    key_x_values = set(span_station_candidates(span, final_moments, left_reaction))
    x_values.update(key_x_values)
    intervals = 48
    for index in range(intervals + 1):
        x_values.add(span.length * index / intervals)
    for _load, distance in getattr(span, 'point_loads', []):
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
    
    # Note: For free ends, span.left or span.right might not be in `supports`
    for span in spans:
        if span.left in supports:
            joint_ends[span.left].append(span.left_end)
        if span.right in supports:
            joint_ends[span.right].append(span.right_end)

    global_x = 0.0
    max_shear = {"span": "", "x": 0.0, "value": 0.0}
    max_moment = {"span": "", "x": 0.0, "value": 0.0}

    # If first span has left free end, global_x is 0 at the free end. 
    # Support positions should track actual supports.
    # We will just record support_positions for actual supports
    
    for span in spans:
        span_start = global_x
        if span.left in supports and not any(s["name"] == span.left for s in support_positions):
            support_positions.append({"name": span.left, "x": global_x})
            
        left_reaction, right_reaction = span_reactions(span, final_moments)
        if span.left in support_reactions:
            support_reactions[span.left] += left_reaction
            support_reaction_parts[span.left].append((span.name, left_reaction))
        if span.right in support_reactions:
            support_reactions[span.right] += right_reaction
            support_reaction_parts[span.right].append((span.name, right_reaction))

        total_load = total_span_load(span)
        load_moment = load_moment_about_left(span)
        reaction_calc_rows.append(
            [
                span.name,
                "Right reaction",
                "\\(R_R=(\\Sigma W x + M_L + M_R)/L\\)",
                (
                    f"\\(({money(load_moment)} + {money(final_moments.get(span.left_end, 0.0))} + "
                    f"{money(final_moments.get(span.right_end, 0.0))})/{fmt(span.length)}\\)"
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
            
            if 0.0 < l_val < span.length and not any(math.isclose(l_val, pt[1], abs_tol=1e-6) for pt in getattr(span, 'point_loads', [])):
                if math.isclose(shear_at(span, left_reaction, l_val), 0.0, abs_tol=1e-6) and getattr(span, 'udls', []):
                    start_val = max([0.0] + [pt[1] for pt in span.point_loads if pt[1] < l_val]
                                    + [a for _w, a, _b in span.udls if a < l_val])
                    shear_start = shear_at(span, left_reaction, start_val, after_point_loads=True)
                    active_w = sum(w for w, a, b in span.udls if a <= l_val <= b)
                    if active_w > 0:
                        zero_shear_calcs.append({
                            "span": span.name,
                            "start": start_val,
                            "v_start": shear_start,
                            "udl": active_w,
                            "root": l_val
                        })

        shear_checks = [(0.0, True), (span.length, True)]
        for _load, distance in getattr(span, 'point_loads', []):
            shear_checks.append((distance, False))
            shear_checks.append((distance, True))
        for x, after_point_loads in shear_checks:
            shear = shear_at(span, left_reaction, x, after_point_loads=after_point_loads)
            if abs(shear) > abs(max_shear["value"]):
                max_shear = {"span": span.name, "x": x, "value": shear}

        total_udl_w = sum(w for w, a, b in getattr(span, 'udls', []) if span._is_full_span_udl(a, b))
        has_partial = any(not span._is_full_span_udl(a, b) for w, a, b in getattr(span, 'udls', []))
        if has_partial:
            udl_term_generic = "-\\Sigma w_i(l-a_i)"
            udl_parts = []
            for w, a, b in span.udls:
                if span._is_full_span_udl(a, b):
                    udl_parts.append(f"{money(w)}l")
                else:
                    udl_parts.append(f"{money(w)}(l-{fmt(a)})" if a > 0 else f"{money(w)}l")
            udl_term_specific = "-" + "-".join(udl_parts) if udl_parts else ""
        elif total_udl_w > 0:
            udl_term_generic = "-wl"
            udl_term_specific = f"-{money(total_udl_w)}l"
        else:
            udl_term_generic = ""
            udl_term_specific = ""

        shear_calc_rows.append(
            [
                span.name,
                f"\\(V(l)=R_L{udl_term_generic}-\\Sigma P_{{a\\le l}}\\)",
                f"\\(V(l)={money(left_reaction)}{udl_term_specific}-\\Sigma P\\)",
            ]
        )
        for l_val in station_candidates:
            point_load_sum = sum(load for load, distance in getattr(span, 'point_loads', []) if distance <= l_val)
            l_str = f"\\frac{{{money(span.length)}}}{{2}}" if math.isclose(l_val, span.length / 2, abs_tol=1e-6) else money(l_val)
            udl_contrib = 0.0
            for w, a, b in getattr(span, 'udls', []):
                if l_val <= a:
                    pass
                elif l_val <= b:
                    udl_contrib += w * (l_val - a)
                else:
                    udl_contrib += w * (b - a)
            shear_calc_rows.append(
                [
                    f"{span.name} at l={l_str}",
                    "\\(V=R_L-\\Sigma w-\\Sigma P\\)",
                    f"\\({money(left_reaction)}-{money(udl_contrib)}-{money(point_load_sum)}={money(shear_at(span, left_reaction, l_val))}\\)",
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
        prev_M = final_moments.get(span.left_end, 0.0)
        
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
            
            if not getattr(span, 'udls', []) and math.isclose(v_start, v_end, abs_tol=1e-6):
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
        
        if span.right in supports and not any(s["name"] == span.right for s in support_positions):
            support_positions.append({"name": span.right, "x": global_x})
            
        span_infos.append(
            {
                "name": span.name,
                "left": span.left,
                "right": span.right,
                "length": span.length,
                "start": span_start,
                "end": global_x,
                "udls": [{"w": w, "a": a, "b": b} for w, a, b in getattr(span, 'udls', [])],
                "point_loads": [{"load": load, "distance": distance} for load, distance in getattr(span, 'point_loads', [])],
                "left_reaction": left_reaction,
                "right_reaction": right_reaction,
                "ml": final_moments.get(span.left_end, 0.0),
                "mr": final_moments.get(span.right_end, 0.0),
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
        if not joint_ends[support]:
            continue
        residual = sum(final_moments.get(end, 0.0) for end in joint_ends[support])
        is_exterior_support = support in {supports[0], supports[-1]}
        status = "Fixed-end support moment" if is_exterior_support and abs(residual) >= 1e-4 else ("Balanced" if abs(residual) < 1e-4 else "Residual moment remains")
        equilibrium_rows.append(
            [
                support,
                "Residual joint moment",
                "\\(\\Sigma M_{joint}\\)",
                "\\(" + "+".join(money(final_moments.get(end, 0.0)) for end in joint_ends[support]) + "\\)",
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
    ]
    if supports and support_reactions:
        summary_rows.append(["Maximum support reaction", max(support_reactions.items(), key=lambda item: abs(item[1]))[0], "Support", money(max(support_reactions.values(), key=abs))])
    
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


def fixed_end_detail_rows(span: Span) -> List[List[Any]]:
    is_left_overhang = getattr(span, 'is_left_overhang', None)
    is_right_overhang = (is_left_overhang is False)
    is_left_overhang = (is_left_overhang is True)
    
    rows: List[List[Any]] = []
    udls = getattr(span, 'udls', [])
    point_loads = getattr(span, 'point_loads', [])
    base_rows = 2 * len(udls) + 2 * len(point_loads)
    total_rows = 2 if base_rows == 0 else (base_rows + (2 if base_rows > 2 else 0))
    
    span_val = {"value": span.name, "rowspan": total_rows}
    L = span.length

    for udl_idx, (w, a, b) in enumerate(udls, start=1):
        if is_left_overhang:
            left_value = 0.0
            right_value = w * (L * (b - a) - (b**2 - a**2) / 2.0)
            label = "UDL" if len(udls) == 1 else f"UDL {udl_idx}"
            range_str = f"({fmt(a)}m–{fmt(b)}m)"
            rows.append([span_val, {"value": f"{label} {range_str}", "rowspan": 2}, span.left_end, "\\(0\\)", "\\(0\\)", money(0.0)])
            span_val = None
            rows.append([span_val, None, span.right_end, "\\(w(L(b-a)-\\frac{b^2-a^2}{2})\\)", f"\\({fmt(w)}({fmt(L)}({fmt(b)}-{fmt(a)})-\\frac{{{fmt(b)}^2-{fmt(a)}^2}}{{2}})\\)", money(right_value)])
        elif is_right_overhang:
            left_value = -w * (b**2 - a**2) / 2.0
            right_value = 0.0
            label = "UDL" if len(udls) == 1 else f"UDL {udl_idx}"
            range_str = f"({fmt(a)}m–{fmt(b)}m)"
            rows.append([span_val, {"value": f"{label} {range_str}", "rowspan": 2}, span.left_end, "\\(-w\\frac{b^2-a^2}{2}\\)", f"\\(-{fmt(w)}\\frac{{{fmt(b)}^2-{fmt(a)}^2}}{{2}}\\)", money(left_value)])
            span_val = None
            rows.append([span_val, None, span.right_end, "\\(0\\)", "\\(0\\)", money(0.0)])
        elif span._is_full_span_udl(a, b):
            left_value = -(w * L**2) / 12.0
            right_value = (w * L**2) / 12.0
            label = "UDL" if len(udls) == 1 else f"UDL {udl_idx}"
            rows.append(
                [
                    span_val,
                    {"value": label, "rowspan": 2},
                    span.left_end,
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
                    span.right_end,
                    "\\(wL^2/12\\)",
                    f"\\(({fmt(w)} \\times {fmt(L)}^2) / 12\\)",
                    money(right_value),
                ]
            )
        else:
            b2_a2 = b**2 - a**2
            b3_a3 = b**3 - a**3
            b4_a4 = b**4 - a**4
            left_value = -(w / L**2) * (L**2 * b2_a2 / 2.0 - 2.0 * L * b3_a3 / 3.0 + b4_a4 / 4.0)
            right_value = (w / L**2) * (L * b3_a3 / 3.0 - b4_a4 / 4.0)
            label = f"UDL {udl_idx}" if len(udls) > 1 else "UDL"
            range_str = f"({fmt(a)}m–{fmt(b)}m)"
            rows.append(
                [
                    span_val,
                    {"value": f"{label} {range_str}", "rowspan": 2},
                    span.left_end,
                    "\\(-\\frac{w}{L^2}[\\frac{L^2}{2}(b^2-a^2)-\\frac{2L}{3}(b^3-a^3)+\\frac{1}{4}(b^4-a^4)]\\)",
                    f"\\(-\\frac{{{fmt(w)}}}{{{fmt(L)}^2}}[\\frac{{{fmt(L)}^2}}{{2}}({fmt(b)}^2-{fmt(a)}^2)-\\frac{{2({fmt(L)})}}{{3}}({fmt(b)}^3-{fmt(a)}^3)+\\frac{{1}}{{4}}({fmt(b)}^4-{fmt(a)}^4)]\\)",
                    money(left_value),
                ]
            )
            span_val = None
            rows.append(
                [
                    span_val,
                    None,
                    span.right_end,
                    "\\(\\frac{w}{L^2}[\\frac{L}{3}(b^3-a^3)-\\frac{1}{4}(b^4-a^4)]\\)",
                    f"\\(\\frac{{{fmt(w)}}}{{{fmt(L)}^2}}[\\frac{{{fmt(L)}}}{{3}}({fmt(b)}^3-{fmt(a)}^3)-\\frac{{1}}{{4}}({fmt(b)}^4-{fmt(a)}^4)]\\)",
                    money(right_value),
                ]
            )

    for pl_idx, (load, a) in enumerate(point_loads, start=1):
        if is_left_overhang:
            left_value = 0.0
            right_value = load * (L - a)
            label = "Point" if len(point_loads) == 1 else f"Point {pl_idx}"
            rows.append([span_val, {"value": label, "rowspan": 2}, span.left_end, "\\(0\\)", "\\(0\\)", money(0.0)])
            span_val = None
            rows.append([span_val, None, span.right_end, "\\(P(L-a)\\)", f"\\({fmt(load)}({fmt(L)}-{fmt(a)})\\)", money(right_value)])
        elif is_right_overhang:
            left_value = -load * a
            right_value = 0.0
            label = "Point" if len(point_loads) == 1 else f"Point {pl_idx}"
            rows.append([span_val, {"value": label, "rowspan": 2}, span.left_end, "\\(-Pa\\)", f"\\(-{fmt(load)}\\times {fmt(a)}\\)", money(left_value)])
            span_val = None
            rows.append([span_val, None, span.right_end, "\\(0\\)", "\\(0\\)", money(0.0)])
        else:
            b = L - a
            left_value = -(load * b**2 * a) / L**2
            right_value = (load * a**2 * b) / L**2
            label = "Point" if len(point_loads) == 1 else f"Point {pl_idx}"
            rows.append(
                [
                    span_val,
                    {"value": label, "rowspan": 2},
                    span.left_end,
                    "\\(-Pab^2/L^2\\)",
                    f"\\(-({fmt(load)}\\times {fmt(a)}\\times {fmt(b)}^2)/{fmt(L)}^2\\)",
                    money(left_value),
                ]
            )
            span_val = None
            rows.append(
                [
                    span_val,
                    None,
                    span.right_end,
                    "\\(Pa^2b/L^2\\)",
                    f"\\(({fmt(load)}\\times {fmt(a)}^2\\times {fmt(b)})/{fmt(L)}^2\\)",
                    money(right_value),
                ]
            )

    if not rows:
        rows.append([span_val, {"value": "No load", "rowspan": 2}, span.left_end, "\\(0\\)", "\\(0\\)", money(0.0)])
        span_val = None
        rows.append([span_val, None, span.right_end, "\\(0\\)", "\\(0\\)", money(0.0)])

    left_total, right_total = span.fixed_end_moments()
    if len(rows) > 2:
        rows.append([span_val, {"value": "Total", "rowspan": 2}, span.left_end, "\\(\\Sigma M_L\\)", "sum of left-end contributions", money(left_total)])
        span_val = None
        rows.append([span_val, None, span.right_end, "\\(\\Sigma M_R\\)", "sum of right-end contributions", money(right_total)])
        
    return rows
