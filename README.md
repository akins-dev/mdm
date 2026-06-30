# Moment Distribution Method Calculator

This is a standalone Python browser-GUI program for continuous beam analysis
using the Hardy Cross moment distribution method.

## Run

```bash
python3 mdm.py
```

Then open the local address printed in the terminal, usually:

```text
http://127.0.0.1:8000
```

You can also choose a host or starting port:

```bash
python3 mdm.py --host 127.0.0.1 --port 8000
```

If the selected port is busy, the app tries the next ports automatically.

When installed as a package, the same app can be started with:

```bash
mdm-gui
```

## Test

```bash
python3 -m unittest discover
```

## Project Structure

```text
.
├── mdm.py              # calculation engine, browser UI, and local server
├── tests/              # unit tests for formulas, parsing, and output payloads
├── pyproject.toml      # package metadata and console script
├── README.md
└── .gitignore
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

Point loads are entered in the GUI as `P@a`, where `a` is the distance from the
left support. Separate multiple point loads with semicolons, for example:

```text
12@2; 8@4.5
```

## Outputs

- distribution factor table
- fixed-end moment formula and substitution table
- moment distribution table
- final support moment summary

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
