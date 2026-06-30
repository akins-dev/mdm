from __future__ import annotations
from dataclasses import dataclass, field
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
