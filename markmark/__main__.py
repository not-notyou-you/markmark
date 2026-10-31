import argparse
import os
import webbrowser

from .server import make_server


def main():
    parser = argparse.ArgumentParser(prog="markmark")
    parser.add_argument("--port", type=int, default=int(os.environ.get("MARKMARK_PORT", 8765)))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = make_server(args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Markmark: {url}  (Ctrl+C to stop)")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
