import shutil
import subprocess
from pathlib import Path

import numpy
from matplotlib import pyplot

MIN_FROUDE_NUM = 0.2
MAX_FROUDE_NUM = 3.0

FLAT_PLATE_ROOT = Path(__file__).parent / "flat_plate"


def run_flat_plate(froude_num: float, angle_of_attack: float) -> None:
    if not (MIN_FROUDE_NUM <= froude_num <= MAX_FROUDE_NUM):
        raise ValueError("Input Froude number must be in the range 0.2 <= Fr <= 3.0")

    case_dir_base = FLAT_PLATE_ROOT / "flat_plate_base"

    case_dir = FLAT_PLATE_ROOT / f"Fr={froude_num:0.1f}_AOA={angle_of_attack:0.1f}"
    if not case_dir.exists():
        shutil.copytree(case_dir_base, case_dir)

    with (case_dir / "configDict").open("w") as fp:
        fp.write("baseDict: './configDict.base'\n")
        fp.write(f"Fr: {froude_num}\n")
        fp.write(f"AOA: {angle_of_attack}\n")

    subprocess.run(["planingfsi", "mesh"], cwd=str(case_dir))
    subprocess.run(["planingfsi", "run"], cwd=str(case_dir))

    # Find the latest time directory to load results from
    results_dir = sorted(
        case_dir.glob("[0-9]*"), key=lambda d: int(d.name), reverse=True
    )[0]

    plate_coords = numpy.loadtxt(results_dir / "coords_plate.txt")
    fs_coords = numpy.loadtxt(results_dir / "freeSurface.txt")

    pyplot.plot(plate_coords[:, 0], plate_coords[:, 1], "k-")
    pyplot.plot(fs_coords[:, 0], fs_coords[:, 1], "b-")

    pyplot.show()


if __name__ == "__main__":
    run_flat_plate(froude_num=0.4, angle_of_attack=10.0)
