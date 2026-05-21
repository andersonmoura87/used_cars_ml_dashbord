#!/usr/bin/env python
"""
Inicia o dashboard Streamlit unificado.

Uso:
    python scripts/run_dashboard.py
    python scripts/run_dashboard.py --port 8502
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
HOME = ROOT / "dashboard" / "Home.py"


def main() -> None:
    port = "8501"
    for i, arg in enumerate(sys.argv[1:]):
        if arg in ("--port", "-p") and i + 1 < len(sys.argv[1:]):
            port = sys.argv[i + 2]

    cmd = [
        sys.executable, "-m", "streamlit", "run",
        str(HOME),
        "--server.port", port,
        "--server.headless", "true",
    ]
    print(f"Iniciando dashboard em http://localhost:{port}")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
