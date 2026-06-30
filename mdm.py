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

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple


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


def support_names(count: int) -> List[str]:
    names = []
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i in range(count):
        if i < len(alphabet):
            names.append(alphabet[i])
        else:
            names.append(f"S{i + 1}")
    return names


def read_float(prompt: str, minimum: float | None = None, default: float | None = None) -> float:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = float(raw)
        except ValueError:
            print("Enter a valid number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Enter a value greater than or equal to {minimum}.")
            continue
        return value


def read_int(prompt: str, minimum: int | None = None, default: int | None = None) -> int:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        raw = input(f"{prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Enter a valid whole number.")
            continue
        if minimum is not None and value < minimum:
            print(f"Enter a value greater than or equal to {minimum}.")
            continue
        return value


def read_yes_no(prompt: str, default: bool = True) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{default_text}]: ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("Enter y or n.")


def money(value: float) -> str:
    if abs(value) < 0.0000005:
        value = 0.0
    return f"{value:,.4f}"


def print_table(headers: List[str], rows: Iterable[Iterable[object]]) -> None:
    string_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in string_rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def line(left: str, fill: str, middle: str, right: str) -> str:
        return left + middle.join(fill * (width + 2) for width in widths) + right

    print(line("+", "-", "+", "+"))
    print("| " + " | ".join(header.ljust(widths[i]) for i, header in enumerate(headers)) + " |")
    print(line("+", "-", "+", "+"))
    for row in string_rows:
        print("| " + " | ".join(cell.rjust(widths[i]) for i, cell in enumerate(row)) + " |")
    print(line("+", "-", "+", "+"))


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

    rows: List[List[str]] = [
        ["Fixed-end moments"] + [money(moments[end]) for end in end_labels],
    ]

    cycles_used = 0
    for cycle in range(1, max_cycles + 1):
        cycles_used = cycle
        cycle_changed = False

        for joint in supports:
            if joint in fixed_supports:
                continue

            unbalanced = sum(moments[end] for end in joint_ends[joint])
            if abs(unbalanced) <= tolerance:
                continue

            cycle_changed = True
            balance_row = {end: 0.0 for end in end_labels}
            carry_row = {end: 0.0 for end in end_labels}

            for end in joint_ends[joint]:
                distributed = -unbalanced * distribution_factors[end]
                balance_row[end] += distributed
                moments[end] += distributed

            for end in joint_ends[joint]:
                carried = balance_row[end] * 0.5
                other_end = opposite[end]
                carry_row[other_end] += carried
                moments[other_end] += carried

            rows.append([f"Cycle {cycle}: balance {joint}"] + [money(balance_row[end]) for end in end_labels])
            rows.append([f"Cycle {cycle}: carry-over {joint}"] + [money(carry_row[end]) for end in end_labels])

        max_unbalanced = 0.0
        for joint in supports:
            if joint not in fixed_supports:
                max_unbalanced = max(max_unbalanced, abs(sum(moments[end] for end in joint_ends[joint])))

        if max_unbalanced <= tolerance or not cycle_changed:
            break

    rows.append(["Final moments"] + [money(moments[end]) for end in end_labels])
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


def read_spans(supports: List[str]) -> List[Span]:
    spans: List[Span] = []
    for i in range(len(supports) - 1):
        left = supports[i]
        right = supports[i + 1]
        print(f"\nSpan {left}{right}")
        length = read_float("Length L", minimum=0.000001)
        udl = read_float("Uniformly distributed load w over full span (use 0 if none)", minimum=0.0, default=0.0)
        point_load_count = read_int("Number of point loads on this span", minimum=0, default=0)
        point_loads: List[Tuple[float, float]] = []
        for load_index in range(1, point_load_count + 1):
            load = read_float(f"Point load {load_index} magnitude P", minimum=0.0)
            a = read_float(f"Point load {load_index} distance from {left}", minimum=0.0)
            while a > length:
                print("The distance cannot be longer than the span.")
                a = read_float(f"Point load {load_index} distance from {left}", minimum=0.0)
            point_loads.append((load, a))
        spans.append(Span(left=left, right=right, length=length, udl=udl, point_loads=point_loads))
    return spans


def main() -> None:
    print("Hardy Cross Moment Distribution for Continuous Beams")
    print("Units are not forced. Use one consistent system, e.g. kN and m gives kN-m moments.\n")

    support_count = read_int("Number of supports", minimum=2)
    supports = support_names(support_count)
    print(f"Supports: {', '.join(supports)}")
    print(f"Spans: {', '.join(f'{supports[i]}{supports[i + 1]}' for i in range(support_count - 1))}")

    exterior_fixed = read_yes_no("Are the two exterior supports fixed against rotation?", default=True)
    fixed_supports = {supports[0], supports[-1]} if exterior_fixed else set()

    spans = read_spans(supports)
    tolerance = read_float("\nMoment-distribution tolerance", minimum=0.0, default=0.0001)
    max_cycles = read_int("Maximum distribution cycles", minimum=1, default=50)

    distribution_rows, distribution_factors, joint_ends, opposite = build_distribution_rows(
        spans,
        supports,
        fixed_supports,
    )

    print("\nDistribution Factor Table")
    print_table(
        ["Joint", "Span", "Member end", "Relative stiffness 1/L", "Joint sum", "Distribution factor"],
        distribution_rows,
    )

    headers, md_rows, final_moments, cycles_used = moment_distribution(
        spans,
        supports,
        fixed_supports,
        distribution_factors,
        joint_ends,
        opposite,
        tolerance,
        max_cycles,
    )

    print("\nMoment Distribution Table")
    print_table(headers, md_rows)

    print("\nFinal Support Moment Summary")
    print_table(["Support", "Member-end moments", "Algebraic joint sum"], support_moment_rows(supports, joint_ends, final_moments))
    print(f"\nCompleted in {cycles_used} cycle(s).")


if __name__ == "__main__":
    main()
