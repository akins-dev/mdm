import unittest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from mdm.core import Span, support_names
from mdm.solver import build_standard_distribution_rows
from mdm.server import calculate_from_payload, parse_point_loads

class SpanCalculationTests(unittest.TestCase):
    def test_udl_fixed_end_moments(self) -> None:
        span = Span("A", "B", length=6.0, udl=10.0)

        left, right = span.fixed_end_moments()

        self.assertAlmostEqual(left, -30.0)
        self.assertAlmostEqual(right, 30.0)

    def test_point_load_fixed_end_moments(self) -> None:
        span = Span("B", "C", length=4.0, point_loads=[(12.0, 2.0)])

        left, right = span.fixed_end_moments()

        self.assertAlmostEqual(left, -6.0)
        self.assertAlmostEqual(right, 6.0)

    def test_fixed_end_detail_rows_show_formula_substitution_and_total(self) -> None:
        span = Span("B", "C", length=4.0, udl=8.0, point_loads=[(12.0, 2.0)])

        rows = span.fixed_end_detail_rows()

        self.assertIn(["BC", "UDL", "BC", "\\(-wL^2/12\\)", "\\(-(8 \\times 4^2) / 12\\)", "-10.6667"], rows)
        self.assertIn(["BC", "Point 1", "BC", "\\(-Pab^2/L^2\\)", "\\(-(12 \\times 2 \\times 2^2) / 4^2\\)", "-6.0000"], rows)
        self.assertEqual(rows[-2], ["BC", "Total", "BC", "\\(\\Sigma M_L\\)", "sum of left-end contributions", "-16.6667"])


class MomentDistributionTests(unittest.TestCase):
    def test_distribution_factor_rows_for_two_span_beam(self) -> None:
        spans = [Span("A", "B", 6.0), Span("B", "C", 4.0)]
        supports = support_names(3)

        rows, factors, _joint_ends, _opposite = build_standard_distribution_rows(spans, supports, {"A", "C"})

        self.assertEqual(rows[1], ["B", "BA", "\\(k=1/L=1/6=0.1667\\)", "\\(\\Sigma k=0.4167\\)", "\\(DF=k/\\Sigma k=0.4000\\)"])
        self.assertEqual(rows[2], ["B", "BC", "\\(k=1/L=1/4=0.2500\\)", "\\(\\Sigma k=0.4167\\)", "\\(DF=k/\\Sigma k=0.6000\\)"])
        self.assertAlmostEqual(factors["BA"], 0.4)
        self.assertAlmostEqual(factors["BC"], 0.6)

    def test_payload_calculation_returns_all_output_tables(self) -> None:
        payload = {
            "support_count": 3,
            "exterior_fixed": True,
            "tolerance": "0.0001",
            "max_cycles": 20,
            "spans": [
                {"length": "6", "udl": "10", "point_loads": ""},
                {"length": "4", "udl": "8", "point_loads": "12@2"},
            ],
        }

        result = calculate_from_payload(payload)

        self.assertIn("Calculated 2 span(s)", result["status"])
        self.assertTrue(
            {
                "distribution",
                "fem",
                "moment",
                "reactions",
                "support_reactions",
                "support_reaction_calculations",
                "reaction_calculations",
                "shear_calculations",
                "bending_calculations",
                "equilibrium_checks",
                "shear_values",
                "moment_values",
                "extrema",
                "support",
            }.issubset(result["tables"])
        )
        self.assertEqual(result["tables"]["moment"]["rows"][4][0], "Distribution cycle 1")
        self.assertEqual(result["tables"]["moment"]["rows"][5][0], "Carry over cycle 1")
        self.assertEqual(result["tables"]["moment"]["rows"][-1], ["End Moment", "-32.6667", "24.6667", "-24.6667", "12.6667"])
        self.assertEqual(result["tables"]["support_reactions"]["rows"], [["A", "31.3333"], ["B", "53.6667"], ["C", "19.0000"]])
        self.assertEqual(result["tables"]["support_reaction_calculations"]["rows"][1][-1], "53.6667")
        self.assertEqual(result["tables"]["extrema"]["rows"][0], ["Maximum absolute shear", "AB", "0.0000", "31.3333"])
        self.assertEqual(result["tables"]["equilibrium_checks"]["rows"][0][-1], "Balanced")
        self.assertEqual(result["tables"]["equilibrium_checks"]["rows"][1][-1], "Balanced")
        self.assertIn("shear", result["diagrams"])
        self.assertIn("moment", result["diagrams"])
        self.assertIn("beam", result)
        self.assertEqual(result["diagrams"]["shear"][0]["y"], 0.0)
        self.assertEqual(result["diagrams"]["shear"][-1]["y"], 0.0)
        self.assertEqual(result["beam"]["spans"][0]["name"], "AB")


class InputParsingTests(unittest.TestCase):
    def test_parse_multiple_point_loads(self) -> None:
        self.assertEqual(parse_point_loads("12@2; 8@4.5", 6.0, "AB"), [(12.0, 2.0), (8.0, 4.5)])

    def test_parse_point_load_rejects_distance_outside_span(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and 6"):
            parse_point_loads("12@8", 6.0, "AB")


if __name__ == "__main__":
    unittest.main()
