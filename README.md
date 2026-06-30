# Hardy Cross Moment Distribution

A professional, modular Python web tool for structural beam analysis using the Hardy Cross moment distribution method.

## Features
- **Interactive UI**: Clean, responsive browser-based interface.
- **Accurate Analysis**: Solves continuous beams using the iterative moment distribution method.
- **Detailed Outputs**: Generates Shear Force Diagrams (SFD), Bending Moment Diagrams (BMD), Fixed-End Moments (FEM), and support reactions.
- **Points of Zero Shear**: Calculates and visualizes the points of maximum bending moment.
- **No External Dependencies**: The core server runs purely on Python's standard library.

## Installation
Clone the repository:
```bash
git clone <repository_url>
cd mdm
```

This tool does not require any third-party packages to run. If you wish to run the test suite, install the dependencies in `requirements.txt`:
```bash
pip install -r requirements.txt
```

## Usage
Run the built-in HTTP server:
```bash
python -m src.mdm.main
```
Then, open the provided URL (default: `http://127.0.0.1:8000`) in your web browser.

See `USER_MANUAL.md` for detailed instructions on using the web interface.
See `DEVELOPMENT.md` for information on the project's architecture and how to contribute.
