import os
import runpy


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET_SCRIPT = os.path.join(BASE_DIR, "d-mak.py")


if __name__ == "__main__":
    if not os.path.exists(TARGET_SCRIPT):
        raise FileNotFoundError(f"Monitor script not found: {TARGET_SCRIPT}")
    runpy.run_path(TARGET_SCRIPT, run_name="__main__")
