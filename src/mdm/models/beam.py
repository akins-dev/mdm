from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Any
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
        """Return fixed-end moments (left end, right end)."""
        L = self.length
        fem_left = 0.0
        fem_right = 0.0

        for w, a, b in self.udls:
            b2_a2 = b**2 - a**2
            b3_a3 = b**3 - a**3
            b4_a4 = b**4 - a**4
            fem_left += -(w / L**2) * (L**2 * b2_a2 / 2.0 - 2.0 * L * b3_a3 / 3.0 + b4_a4 / 4.0)
            fem_right += (w / L**2) * (L * b3_a3 / 3.0 - b4_a4 / 4.0)

        for load, a in self.point_loads:
            b = self.length - a
            fem_left += -(load * b**2 * a) / self.length**2
            fem_right += (load * a**2 * b) / self.length**2

        return fem_left, fem_right

    def _is_full_span_udl(self, a: float, b: float) -> bool:
        """Check if a UDL covers the entire span."""
        return math.isclose(a, 0.0, abs_tol=1e-9) and math.isclose(b, self.length, abs_tol=1e-9)


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
