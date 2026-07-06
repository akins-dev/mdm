from typing import List, Dict, Any, Tuple
from ..models.beam import Span
from .base import BeamAnalyzer
from .solver import (
    build_standard_distribution_rows,
    moment_distribution,
    analysis_from_final_moments,
    fixed_end_detail_rows
)

class OverhangingSpan(Span):
    def __init__(self, span: Span, is_left_overhang: bool):
        super().__init__(
            left=span.left, right=span.right, length=span.length,
            udls=span.udls, point_loads=span.point_loads
        )
        self.is_left_overhang = is_left_overhang

    @property
    def stiffness(self) -> float:
        return 0.0

    def fixed_end_moments(self) -> Tuple[float, float]:
        """
        Return the statically determinate cantilever moments.
        If it's a left overhang, the support is at the right end.
        If it's a right overhang, the support is at the left end.
        """
        fem_left = 0.0
        fem_right = 0.0

        if self.is_left_overhang:
            # Support is at right. Free at left.
            # Loads create moment at the right support.
            for w, a, b in self.udls:
                # distance from right support = length - x
                # Integral of w * (L - x) dx from a to b
                # = w * [L*x - x^2/2] from a to b
                # = w * (L*(b-a) - (b^2-a^2)/2)
                fem_right += w * (self.length * (b - a) - (b**2 - a**2) / 2.0)
            
            for load, a in self.point_loads:
                # distance from right support = length - a
                fem_right += load * (self.length - a)
                
            # To balance this moment, the support must exert a clockwise moment
            fem_right = fem_right
            fem_left = 0.0
        else:
            # Support is at left. Free at right.
            # Loads create moment at the left support.
            for w, a, b in self.udls:
                # distance from left support = x
                # Integral of w * x dx from a to b
                fem_left += w * (b**2 - a**2) / 2.0
                
            for load, a in self.point_loads:
                # distance from left support = a
                fem_left += load * a
                
            # To balance this moment, the support must exert a counter-clockwise moment (negative)
            fem_left = -fem_left
            fem_right = 0.0

        return fem_left, fem_right


class OverhangingAnalyzer(BeamAnalyzer):
    def __init__(self, overhang_type: str = "left"):
        self.overhang_type = overhang_type
        
    def analyze(self, spans: List[Span], supports: List[str], fixed_supports: List[str], **kwargs) -> Dict[str, Any]:
        tolerance = kwargs.get("tolerance", 0.0001)
        max_cycles = kwargs.get("max_cycles", 100)
        
        # Modify spans based on overhang type
        modified_spans = []
        for i, span in enumerate(spans):
            is_first = (i == 0)
            is_last = (i == len(spans) - 1)
            
            if is_first and self.overhang_type in ["left", "both"]:
                modified_spans.append(OverhangingSpan(span, is_left_overhang=True))
            elif is_last and self.overhang_type in ["right", "both"]:
                modified_spans.append(OverhangingSpan(span, is_left_overhang=False))
            else:
                modified_spans.append(span)

        # Filter out the free ends from the `supports` list so MDM doesn't balance them
        active_supports = list(supports)
        if self.overhang_type in ["left", "both"]:
            active_supports.remove(spans[0].left)
        if self.overhang_type in ["right", "both"]:
            active_supports.remove(spans[-1].right)

        distribution_rows, distribution_factors, joint_ends, opposite = build_standard_distribution_rows(
            modified_spans, active_supports, set(fixed_supports)
        )
        
        md_headers, md_rows, final_moments, cycles_used = moment_distribution(
            modified_spans,
            active_supports,
            set(fixed_supports),
            distribution_factors,
            joint_ends,
            opposite,
            tolerance,
            max_cycles,
        )
        
        analysis = analysis_from_final_moments(modified_spans, active_supports, final_moments)

        return {
            "status": (
                f"Calculated overhanging beam with {len(modified_spans)} span(s). "
                f"Moment distribution completed in {cycles_used} cycle(s)."
            ),
            "tabs": {
                "distribution": "Distribution Factors",
                "fem": "Fixed-End Moment Calculations",
                "moment": "Moment Distribution",
                "reactions": "Reactions",
                "diagrams": "SFD / BMD",
                "design": "RC Design",
                "values": "Values"
            },
            "tables": {
                "distribution": {
                    "headers": ["Joints", "Member", "Stiffness \\(k = 1/L\\)", "\\(\\Sigma k\\)", "DF \\( = k / \\Sigma k\\)"],
                    "rows": distribution_rows,
                },
                "fem": {
                    "headers": ["Span", "Load", "End", "Formula", "Substitution", "Moment (kNm)"],
                    "rows": [row for span in modified_spans for row in fixed_end_detail_rows(span)],
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
                    "headers": ["Result", "Span", "Distance from free/left end (m)", "Value"],
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
                    "headers": ["Result", "Span", "x from free/left end (m)", "Value"],
                    "rows": analysis["summary_rows"],
                },
            },
            "diagrams": analysis["diagrams"],
            "beam": analysis["beam"]
        }
