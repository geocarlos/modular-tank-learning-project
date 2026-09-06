import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "out"
SRC_DIR = ROOT / "src"

# Order matters: each script after the first references .usda files
# produced by an earlier one (chassis/track/turret -> assembly/rig -> motion).
SCRIPTS = [
    "chassis.py",
    "track.py",
    "turret_assembly.py",
    "master_assembly.py",
    "rigging_and_hierarchy.py",
    "setup_and_motion.py",
]


def main():
    OUT_DIR.mkdir(exist_ok=True)
    # Usd.Stage.CreateNew refuses to overwrite an existing layer, so clear
    # previous output before regenerating.
    for usda_file in OUT_DIR.glob("*.usda"):
        usda_file.unlink()

    for script in SCRIPTS:
        print(f"Running {script}...")
        subprocess.run([sys.executable, str(SRC_DIR / script)], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
