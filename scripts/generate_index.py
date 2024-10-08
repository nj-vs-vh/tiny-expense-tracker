import argparse
from pathlib import Path

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("backend_host")

    args = parser.parse_args()

    host: str = args.backend_host
    host = host.rstrip("/")
    print(f"Rendering index.html with backend host = {host!r}")

    root = Path(__file__).parent.parent
    frontend_dir = root / "frontend"
    index_template = frontend_dir / "index.local.html"
    index_body = index_template.read_text()
    index_body = index_body.replace("__replacedOnRender__", '"' + host + '"')
    (frontend_dir / "index.html").write_text(index_body)
    print("OK")
