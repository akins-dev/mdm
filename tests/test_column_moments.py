"""
Phase-1 gate for the column moment engine.

Non-negotiable: reproduce the office-block worked example (Oyenuga Ch.7, as
verified in COLUMN_MOMENT_RESEARCH.md) to 3 s.f. — the single-joint distribution
is the heart of the whole feature.

Run:  python -m pytest tests/test_column_moments.py -q
  or: python tests/test_column_moments.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from mdm.design.column_moments import (
    Beam,
    Lift,
    Joint,
    single_joint_distribution,
    slab_to_beam_udl,
    slab_beam_share,
    analyze_column_stack,
)
from mdm.design.bs8110 import beta_effective_length, biaxial_beta


def _beam(axis, side, span, target_fem, target_K):
    """Beam whose full-UDL FEM == target_fem (kNm) and I/L == target_K (mm^3)."""
    w = target_fem * 12.0 / span ** 2
    I_override = target_K * span * 1000.0
    return Beam(axis=axis, side=side, span=span, w=w, b=300.0, h=600.0,
               I_override=I_override)


class SingleJointDistribution(unittest.TestCase):
    """The verified formula: M_col = M_unbal * K_col / (SigmaK_cols + SigmaK_beams)."""

    def test_office_block_A1_roof(self):
        # 18.13 * 71.19 / (71.19 + 341.7 + 284.8) = 1.85
        shares = single_joint_distribution(
            18.13, {"col_below": 71.19, "beam5": 341.7, "beam6": 284.8})
        self.assertAlmostEqual(shares["col_below"], 1.85, places=2)

    def test_office_block_A1_2nd_floor_both_columns(self):
        # lower col: 79.81*71.19/2618.99 = 2.17 ; upper col: 79.81*67.80/2618.99 = 2.066
        shares = single_joint_distribution(
            79.81, {"col_below": 71.19, "col_above": 67.80,
                    "beam1": 1322.0, "beam2": 1158.0})
        self.assertAlmostEqual(shares["col_below"], 2.17, places=2)
        self.assertAlmostEqual(shares["col_above"], 2.066, places=2)


class DriverReproducesOfficeBlock(unittest.TestCase):
    """Same numbers, but end-to-end through Beam/Lift/Joint (units self-consistent)."""

    def test_roof_joint(self):
        roof = Lift("roofcol", 3.0, b=225.0, h=225.0)   # I = b h^3/12 = 213.6e6
        joint = Joint("roof", lift_below=roof, lift_above=None, beams=[
            _beam("x", +1, 6.0, target_fem=18.13, target_K=341_700.0),
            _beam("y", +1, 6.0, target_fem=40.0, target_K=284_800.0),
        ])
        results, _ = analyze_column_stack([joint], halve_beam_stiffness=False)
        self.assertAlmostEqual(results["roofcol"]["Mx_top"], 1.85, places=2)

    def test_2nd_floor_joint_splits_upper_and_lower(self):
        lower = Lift("lower", 3.0, b=225.0, h=225.0)    # K_x = 71.2e3
        upper = Lift("upper", 3.15, b=225.0, h=225.0)   # K_x = 67.8e3
        joint = Joint("2nd", lift_below=lower, lift_above=upper, beams=[
            _beam("x", +1, 5.0, target_fem=79.81, target_K=1_322_000.0),
            _beam("y", +1, 5.0, target_fem=50.0, target_K=1_158_000.0),
        ])
        results, _ = analyze_column_stack([joint], halve_beam_stiffness=False)
        self.assertAlmostEqual(results["lower"]["Mx_top"], 2.17, places=2)
        self.assertAlmostEqual(results["upper"]["Mx_bot"], 2.066, places=2)


class EdgeCasesByConstruction(unittest.TestCase):
    def test_equal_opposite_beams_cancel(self):
        col = Lift("c", 3.0, 300.0, 300.0)
        joint = Joint("internal", lift_below=col, lift_above=None, beams=[
            _beam("x", +1, 5.0, target_fem=60.0, target_K=500_000.0),
            _beam("x", -1, 5.0, target_fem=60.0, target_K=500_000.0),
        ])
        results, _ = analyze_column_stack([joint])
        self.assertAlmostEqual(results["c"]["Mx_top"], 0.0, places=6)

    def test_unequal_opposite_beams_leave_small_moment(self):
        col = Lift("c", 3.0, 300.0, 300.0)
        joint = Joint("edge", lift_below=col, lift_above=None, beams=[
            _beam("x", +1, 5.0, target_fem=60.0, target_K=500_000.0),
            _beam("x", -1, 5.0, target_fem=40.0, target_K=500_000.0),
        ])
        results, _ = analyze_column_stack([joint])
        self.assertGreater(results["c"]["Mx_top"], 0.0)


class SlabToBeamIdealisation(unittest.TestCase):
    def test_two_way_split_k_1p2(self):
        # w*lx = 62.5, k = ly/lx = 1.2  ->  short 20.83, long 24.02
        self.assertAlmostEqual(slab_to_beam_udl(12.5, 5.0, 6.0, "short"), 20.83, places=2)
        self.assertAlmostEqual(slab_to_beam_udl(12.5, 5.0, 6.0, "long"), 24.02, places=2)


class SlabBeamShareFromGeometry(unittest.TestCase):
    """One/two-way classification and the side falls out of the two spans."""

    def test_two_way_long_edge_is_trapezoid(self):
        # beam 6 m, perp 5 m -> panel lx=5, ly=6, k=1.2 <=2, beam is long edge.
        share, d = slab_beam_share(6.0, 5.0, 12.5)   # long-edge = long-span
        self.assertTrue(d["two_way"])
        self.assertTrue(d["long_edge"])
        self.assertAlmostEqual(share, slab_to_beam_udl(12.5, 5.0, 6.0, "long"), places=6)

    def test_two_way_short_edge_is_triangle(self):
        # beam 5 m, perp 6 m -> beam is the short edge -> triangular w = n*lx/3.
        share, d = slab_beam_share(5.0, 6.0, 12.5)
        self.assertTrue(d["two_way"])
        self.assertFalse(d["long_edge"])
        self.assertAlmostEqual(share, 12.5 * 5.0 / 3.0, places=6)

    def test_one_way_supporting_vs_parallel(self):
        # k = 6/2 = 3 > 2 -> one-way. Long-edge (6 m) beam supports: 0.5*n*lx.
        s_sup, d_sup = slab_beam_share(6.0, 2.0, 10.0)
        self.assertFalse(d_sup["two_way"])
        self.assertAlmostEqual(s_sup, 0.5 * 10.0 * 2.0, places=6)
        # Short-edge (2 m) beam runs parallel to the span -> nominal (0).
        s_par, d_par = slab_beam_share(2.0, 6.0, 10.0)
        self.assertFalse(d_par["two_way"])
        self.assertEqual(s_par, 0.0)

    def test_no_panel_when_no_perpendicular_beam(self):
        share, d = slab_beam_share(6.0, 0.0, 12.5)
        self.assertEqual(share, 0.0)
        self.assertIsNone(d)


class BetaTables(unittest.TestCase):
    def test_braced_table_3_19(self):
        self.assertEqual(beta_effective_length(True, 1, 1), 0.75)
        self.assertEqual(beta_effective_length(True, 2, 3), 0.95)   # bug case: not 0.90
        self.assertEqual(beta_effective_length(True, 3, 3), 1.00)   # bug case: not 0.90

    def test_unbraced_table_3_20(self):
        self.assertEqual(beta_effective_length(False, 1, 1), 1.2)
        self.assertEqual(beta_effective_length(False, 1, 3), 1.6)   # bug case: not 2.0
        self.assertEqual(beta_effective_length(False, 4, 1), 2.2)   # bug case: not 2.0

    def test_biaxial_beta_table_3_22(self):
        self.assertAlmostEqual(biaxial_beta(0.0), 1.00, places=2)
        self.assertAlmostEqual(biaxial_beta(0.3), 0.65, places=2)
        self.assertAlmostEqual(biaxial_beta(0.6), 0.30, places=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
