import sys
import subprocess
from pathlib import Path


def main():
    app_dir = Path(__file__).resolve().parent.parent
    app_script = app_dir / "app.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app_script)])


if __name__ == "__main__":
    main()
