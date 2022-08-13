# Concepts

## Case handlers

`lembas` represents parametrized **types** of analyses via the concept of a case handler.
A case handler is analogous to a "workflow" in other frameworks, and is a collection of **steps**
organized to attain a single goal.

For example, consider the following case handler:

```python
from lembas import Case, InputParameter, step

class HelloCase(Case):
    name = InputParameter(default="Anonymous")

    @step
    def say_hello(self):
        print(f"Hello {self.name}!")
```

The case handler may be run by constructing an instance and calling the
[`run()`](lembas.core.Case.run) method:

```python
case = HelloCase()
case.run()  # prints "Hello Anonymous!"

case = HelloCase(name="Mike")
case.run()  # prints "Hello Mike!"
```

```{note}
In this case, `name` is an optional parameter because a `default` is defined
```

That is not very interesting.
Let's create and run multiple cases in one go!

The container for a list of cases is [`CaseList`](lembas.CaseList), and we can quickly add a
parameter sweep.
The call to [`cases.add_cases_by_parameter_sweep()`](lembas.CaseList.add_cases_by_parameter_sweep)
is a shortcut for adding a sweep of cases across multiple iterables.
For a single parameter, we can iterate over `name` by passing in a list, and the call to
[`cases.run_all()`](lembas.CaseList.run_all) will run each case in succession.

```python
from lembas import CaseList

cases = CaseList()
cases.add_cases_by_parameter_sweep(
    HelloCase,
    name=["Rivers", "Brian", "Scott", "Pat"],
)
cases.run_all()  # prints "Hello Rivers!", "Hello Brian!", ...
```

## Case steps

The above example demonstrates the concept of a `Case`, however its power does not become
apparent until the **step** concept is explained in more detail.
When processing an automated analysis case, it is common to have several **steps** or tasks to
perform.

For example, a hydrodynamic simulation may require the following high-level steps:

1. Prepare the geometry and generate a discretized mesh representation
2. Inject case-specific parameter values into input files, or into an API interface
3. Run the simulation (this step may take a lot of time)
4. Post-process the results by analyzing generated output files and extracting useful information

Each of those steps must be performed for each case, and then frequently at the end we aim to
generate summary results.

```{note}
This example is taken from `examples/planingfsi/flat_plate/run_flat_plate_cases.py`, where a
more complete script can be found.
```

The above steps may be represented as follows, where the details of each step are removed:

```python
class PlaningPlateCase(Case):
    froude_num = InputParameter(type=float, min=0.2, max=3.0)
    angle_of_attack = InputParameter(type=float)

    @step
    def create_input_files(self) -> None:
        ...

    @step
    def generate_mesh(self) -> None:
        ...

    @step
    def run_planingfsi(self) -> None:
        ...

    @step
    def post_process_results(self) -> None:
        ...
```

By default, each `step` will be run in the order in which they are listed.
However, the `@step` decorator can also list steps on which it depends.
In that case, the ordering will be sorted such that dependent steps always run after their
dependencies.

For example:

```python
@step(requires="run_planingfsi")
def post_process_results(self) -> None:
    ...
```

## Conditional steps

By default, a `step` will be run each time the case is run.
However, in the case of restarts, it is often desirable to conditionally run a step based on
some expected output or condition.

For example, in the `PlaningPlateCase` above, the `generate_mesh` step creates a `mesh` directory.
If we re-run the case, we may not want to re-generate the mesh.
In that case, we can add an argument to the `@step` decorator, which is assessed before the step
is performed.
The `condition` is a callable which will receive the `Case` instance as its only argument and
should return a `bool`.

In the example below, the step will only be run if the `mesh` directory does not yet exist.
Thus, the operation is idempotent, i.e. it can be run many times with the same result every time.

```python
@step(condition=lambda case: not (case.case_dir / "mesh").exists())
def generate_mesh(self) -> None:
    ...
```
