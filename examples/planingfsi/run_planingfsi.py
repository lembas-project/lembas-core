from __future__ import annotations

import dataclasses
import functools
import itertools
import shutil
import subprocess
from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy
import pandas
from matplotlib import pyplot
from planingfsi.dictionary import load_dict_from_file

MIN_FROUDE_NUM = 0.2
MAX_FROUDE_NUM = 3.0

FLAT_PLATE_ROOT = Path(__file__).parent / "flat_plate"


@dataclasses.dataclass
class PlaningPlateResults:
    drag: float
    lift: float
    moment: float


class Case:
    """Base case for all cases."""


def step(condition: Callable[[Any], bool]) -> Any:
    def decorator(f: Callable[[Case], None]) -> Callable[[Case], None]:
        @functools.wraps(f)
        def new_f(self: Case) -> None:
            if condition(self):
                return f(self)
            else:
                return None

        return new_f

    return decorator


class PlaningPlateCase(Case):
    def __init__(self, froude_num: float, angle_of_attack: float):
        self.froude_num = froude_num
        self.angle_of_attack = angle_of_attack

    @property
    def case_dir(self) -> Path:
        """The directory in which to run the case."""
        return FLAT_PLATE_ROOT / Path(
            f"Fr={self.froude_num:0.1f}_AOA={self.angle_of_attack:0.1f}"
        )

    @cached_property
    def results(self) -> PlaningPlateResults:
        """Load results from files and return."""
        # Find the latest time directory to load results from
        results_dirs = sorted(
            self.case_dir.glob("[0-9]*"), key=lambda d: int(d.name), reverse=True
        )
        results_dir = results_dirs[0]
        results_dict = load_dict_from_file(results_dir / "forces_total.txt")
        return PlaningPlateResults(
            drag=results_dict["Drag"],
            lift=results_dict["Lift"],
            moment=results_dict["Moment"],
        )

    @step(condition=lambda self: not (self.case_dir / "configDict").exists())
    def _create_input_files(self) -> None:
        print("Creating input files")
        case_dir_base = FLAT_PLATE_ROOT / "flat_plate_base"
        shutil.copytree(case_dir_base, self.case_dir)
        with (self.case_dir / "configDict").open("w") as fp:
            fp.write("baseDict: './configDict.base'\n")
            fp.write(f"Fr: {self.froude_num}\n")
            fp.write(f"AOA: {self.angle_of_attack}\n")

    @step(condition=lambda self: not (self.case_dir / "mesh").exists())
    def _generate_mesh(self) -> None:
        print("Generating mesh")
        subprocess.run(["planingfsi", "mesh"], cwd=str(self.case_dir))

    @step(condition=lambda self: not (self.case_dir / "0").exists())
    def _run_planingfsi(self) -> None:
        print("Running planingfsi")
        subprocess.run(["planingfsi", "run"], cwd=str(self.case_dir))

    def run(self) -> None:
        if not (MIN_FROUDE_NUM <= self.froude_num <= MAX_FROUDE_NUM):
            raise ValueError(
                "Input Froude number must be in the range 0.2 <= Fr <= 3.0"
            )

        self._create_input_files()
        self._generate_mesh()
        self._run_planingfsi()


def main() -> None:
    froude_nums = numpy.linspace(0.5, 3.0, 7)
    AOA_nums = numpy.linspace(5.0, 15.0, 5)

    all_results = []

    for froude_num, aoa in itertools.product(froude_nums, AOA_nums):
        case = PlaningPlateCase(froude_num=froude_num, angle_of_attack=aoa)
        case.run()

        results_dict = dataclasses.asdict(case.results)
        results_dict.update({"froude_num": froude_num, "aoa": aoa})
        all_results.append(results_dict)

    df = pandas.DataFrame.from_records(all_results)
    df.plot.scatter(x="froude_num", y="lift", c="aoa")

    pyplot.show()


if __name__ == "__main__":
    main()
