import dataclasses
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np
import pandas
from matplotlib import pyplot as plt
from planingfsi import FlexibleSubstructure
from planingfsi import Mesh
from planingfsi import Simulation
from planingfsi.fe.felib import Element
from planingfsi.fe.felib import Node
from planingfsi.fe.substructure import Substructure

from lembas import Case
from lembas import InputParameter
from lembas import step

BASE_DIR = Path(__file__).parent


@dataclasses.dataclass
class Coordinate:
    x: float
    y: float


@dataclasses.dataclass
class HydrostaticDamResults:
    max_height: float
    coords: list[Coordinate]


class HydrostaticDamCase(Case):
    waterline_height = InputParameter(type=float)

    @property
    def case_dir(self) -> Path:
        return BASE_DIR / "cases" / f"href={self.waterline_height:0.3f}m"

    @cached_property
    def results(self) -> HydrostaticDamResults:
        """Load results from files and return."""
        # Find the latest time directory to load results from
        results_dirs = sorted(
            self.case_dir.glob("[0-9]*"), key=lambda d: int(d.name), reverse=True
        )
        results_dir = results_dirs[0]
        coords = np.loadtxt(results_dir / "coords_dam.txt")
        return HydrostaticDamResults(
            max_height=np.max(coords[:, 1]),
            coords=[Coordinate(*c) for c in coords],
        )

    @cached_property
    def inputs_dict(self) -> dict[str, Any]:
        """A dictionary of values for each `InputAttribute`."""
        inputs_dict = {}
        for name, attr in self.__class__.__dict__.items():
            if isinstance(attr, InputParameter):
                inputs_dict[name] = getattr(self, name)
        return inputs_dict

    @cached_property
    def results_dict(self) -> dict[str, Any]:
        """A combined dictionary of results & inputs."""
        return dataclasses.asdict(self.results)

    @staticmethod
    def generate_mesh() -> Mesh:
        mesh = Mesh()

        # Create points (ID, type, params)
        mesh.add_point(1, "rel", [0, 0, 1.0])
        mesh.add_point(2, "rel", [0, 180, 1.0])

        dam = mesh.add_submesh("dam")
        dam.add_curve(1, 2, Nel=50, arcLen=np.pi)

        return mesh

    @step(condition=lambda case: not case.case_dir.exists())
    def run(self) -> None:
        # TODO: This can go away once we fix planingfsi
        Node._Node__all.clear()
        Element._Element__all.clear()
        Substructure._Substructure__all.clear()
        FlexibleSubstructure._FlexibleSubstructure__all.clear()

        mesh = self.generate_mesh()

        simulation = Simulation()
        simulation.case_dir = self.case_dir

        # Set some global configuration values
        simulation.config.flow.froude_num = 1.0
        simulation.config.flow.waterline_height = self.waterline_height
        simulation.config.plotting._pressure_scale_pct = 1e-8
        simulation.config.solver.max_it = 500

        body = simulation.add_rigid_body()
        body.add_substructure(
            FlexibleSubstructure(
                name="dam",
                seal_pressure_method="hydrostatic",
            )
        )

        simulation.load_mesh(mesh)
        simulation.run()


def plot_summary_results(cases: list[HydrostaticDamCase]) -> None:
    fig, ax = plt.subplots(2, 1)
    df = pandas.DataFrame.from_records(
        case.inputs_dict | case.results_dict for case in cases
    ).drop(columns="coords")
    df.plot(x="waterline_height", y="max_height", ax=ax[0])
    for case in cases:
        coords_df = pandas.DataFrame.from_records(case.results_dict["coords"])
        coords_df.plot(x="x", y="y", ax=ax[1], label=f"{case.waterline_height:0.1f}m")
    ax[1].axis("equal")
    plt.show()


def main() -> None:
    cases = [
        HydrostaticDamCase(waterline_height=h_ref)
        for h_ref in np.arange(0.8, 10.1, 0.2)
    ]
    for case in cases:
        case.run()

    plot_summary_results(cases)


if __name__ == "__main__":
    main()
