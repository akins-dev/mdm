# Development Guide

This document outlines the architecture and development guidelines for the Hardy Cross Moment Distribution project.

## Architecture
The application is structured into a modular Python package located in `src/mdm/`:
- `core.py`: Contains foundational data structures like the `Span` dataclass, and utility formatting functions.
- `solver.py`: Houses all structural engineering logic, including fixed-end moments calculation, distribution factors, the iterative Hardy Cross moment distribution algorithm, and equations for shear forces, bending moments, and reactions.
- `server.py`: Defines the HTTP request handler, input payload parsing, and serves the REST JSON endpoint (`/calculate`) along with the HTML front-end.
- `main.py`: The application entry point, which provides a command-line interface to start the server.
- `templates/index.html`: The monolithic front-end application built with Vanilla HTML/JS/CSS. It renders the user interface, makes API requests, and visualizes the beam, diagrams, and calculated data tables.

## Testing
Unit tests are written using `pytest` and are located in the `tests/` directory.
Run the test suite using:
```bash
pytest tests/
```

## Modifying the Front-End
The entire UI is served from `src/mdm/templates/index.html`. It uses plain JavaScript without a build step or external frameworks. MathJax is loaded via CDN for LaTeX math rendering. Be sure to update `index.html` cautiously as it tightly couples the presentation with the calculation output structures.
