from typing import Dict, List, Any
from ..models.beam import Span
from .base import BeamAnalyzer
from .solver import (
    build_standard_distribution_rows,
    moment_distribution,
    analysis_from_final_moments,
    fixed_end_detail_rows
)

class ContinuousAnalyzer(BeamAnalyzer):
    def analyze(self, spans: List[Span], supports: List[str], fixed_supports: List[str], **kwargs) -> Dict[str, Any]:
        tolerance = kwargs.get("tolerance", 0.0001)
        max_cycles = kwargs.get("max_cycles", 100)

        distribution_rows, distribution_factors, joint_ends, opposite = build_standard_distribution_rows(
            spans, supports, set(fixed_supports)
        )
        md_headers, md_rows, final_moments, cycles_used = moment_distribution(
            spans,
            supports,
            set(fixed_supports),
            distribution_factors,
            joint_ends,
            opposite,
            tolerance,
            max_cycles,
        )
        analysis = analysis_from_final_moments(spans, supports, final_moments)

        return {
            "status": (
                f"Calculated {len(spans)} span(s) across {len(supports)} supports. "
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
                    "rows": [row for span in spans for row in fixed_end_detail_rows(span)],
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
            },
            "diagrams": analysis["diagrams"],
            "beam": analysis["beam"]
        }
