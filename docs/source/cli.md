# Running cases from the command-line interface

Example of running a `PlaningPlateCase` as-defined in `examples/planingfsi/flat_plate/run_flat_plate_cases.py`.
We must load all case handlers from a file via the `--plugin` option.
We must explicitly specify the case handler to use.
All parameters may be specified via `{name}={value}` arguments.

```shell
lembas run PlaningPlateCase --plugin some_local_file.py froude_num=0.5 angle_of_attack=10
```
