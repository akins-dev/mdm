import argparse
import sys
from pathlib import Path

# Add the 'src' directory to the Python path so this can be run directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mdm.server import create_server

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Hardy Cross moment distribution browser GUI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="Preferred port. Default: 8000")
    parser.add_argument(
        "--port-attempts",
        type=int,
        default=10,
        help="Number of sequential ports to try if the preferred port is busy. Default: 10",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    server, port = create_server(args.host, args.port, args.port_attempts)

    print("Hardy Cross Moment Distribution GUI")
    print(f"Open http://{args.host}:{port} in your browser.")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
