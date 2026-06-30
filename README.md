# Moment Distribution Method Calculator

This is a standalone Python CLI program for continuous beam analysis using the
Hardy Cross moment distribution method.

## Run

```bash
python3 mdm.py
```

## Inputs

- number of supports
- span lengths
- uniformly distributed load on each span, if any
- point loads on each span, if any
- convergence tolerance
- maximum number of distribution cycles

The program automatically names supports `A`, `B`, `C`, and so on. Spans are
named from their end supports, such as `AB` and `BC`.

## Assumptions

- Clockwise member-end moments are positive.
- Relative stiffness is `1/L`, as requested.
- Fixed-ended member carry-over factor is `1/2`.
- Exterior supports default to fixed against rotation, so their distribution
  factor is zero. Internal continuous joints are balanced by moment distribution.
- Uniform loads are assumed to act over the full span.
- Loads should be entered consistently. For example, `kN` and `m` produce
  moments in `kN-m`.

## Fixed-End Moment Formulas

For a full-span UDL:

```text
left end  = -wL^2 / 12
right end =  wL^2 / 12
```

For a point load `P` at distance `a` from the left support, with `b = L - a`:

```text
left end  = -Pab^2 / L^2
right end =  Pa^2b / L^2
```
