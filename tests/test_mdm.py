import unittest

import mdm


class SpanCalculationTests(unittest.TestCase):
    def test_udl_fixed_end_moments(self) -> None:
        span = mdm.Span("A", "B", length=6.0, udl=10.0)

        left, right = span.fixed_end_moments()

        self.assertAlmostEqual(left, -30.0)
        self.assertAlmostEqual(right, 30.0)

    def test_point_load_fixed_end_moments(self) -> None:
        span = mdm.Span("B", "C", length=4.0, point_loads=[(12.0, 2.0)])

        left, right = span.fixed_end_moments()

        self.assertAlmostEqual(left, -6.0)
        self.assertAlmostEqual(right, 6.0)

    def test_fixed_end_detail_rows_show_formula_substitution_and_total(self) -> None:
        span = mdm.Span("B", "C", length=4.0, udl=8.0, point_loads=[(12.0, 2.0)])

        rows = span.fixed_end_detail_rows()

        self.assertIn(["BC", "UDL", "BC", "-wL^2/12", "-(8 x 4^2) / 12", "-10.6667"], rows)
        self.assertIn(["BC", "Point 1", "BC", "-Pab^2/L^2", "-(12 x 2 x 2^2) / 4^2", "-6.0000"], rows)
        self.assertEqual(rows[-2], ["BC", "Total", "BC", "sum", "sum of left-end contributions", "-16.6667"])


class MomentDistributionTests(unittest.TestCase):
    def test_distribution_factor_rows_for_two_span_beam(self) -> None:
        spans = [mdm.Span("A", "B", 6.0), mdm.Span("B", "C", 4.0)]
        supports = mdm.support_names(3)

        rows, factors, _joint_ends, _opposite = mdm.build_distribution_rows(spans, supports, {"A", "C"})

        self.assertEqual(rows[1], ["B", "AB", "BA", "0.1667", "0.4167", "0.4000"])
        self.assertEqual(rows[2], ["B", "BC", "BC", "0.2500", "0.4167", "0.6000"])
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

        result = mdm.calculate_from_payload(payload)

        self.assertIn("Calculated 2 span(s)", result["status"])
        self.assertEqual(set(result["tables"]), {"distribution", "fem", "moment", "support"})
        self.assertEqual(result["tables"]["moment"]["rows"][-1], ["Final moments", "-32.6667", "24.6667", "-24.6667", "12.6667"])


class InputParsingTests(unittest.TestCase):
    def test_parse_multiple_point_loads(self) -> None:
        self.assertEqual(mdm.parse_point_loads("12@2; 8@4.5", 6.0, "AB"), [(12.0, 2.0), (8.0, 4.5)])

    def test_parse_point_load_rejects_distance_outside_span(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 0 and 6"):
            mdm.parse_point_loads("12@8", 6.0, "AB")


if __name__ == "__main__":
    unittest.main()
