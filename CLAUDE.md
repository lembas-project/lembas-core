# lembas-core

Python framework for defining and running parametric engineering analysis.

## Development

### Environment setup

This project uses [pixi](https://pixi.sh) for environment management. All environments are locked via `pixi.lock`.

```bash
# Install dependencies and create environment
pixi install

# Run commands in the environment
pixi run python ...
pixi run pytest
pixi run <task>

# Enter a shell with the environment activated
pixi shell
```

**Never install packages via `pip install` directly.** Add dependencies to `pixi.toml` and run `pixi install`.

### Running tests

```bash
pixi run test
pixi run test-cov  # with coverage
```

### Type checking

```bash
pixi run typecheck
```

### Linting

```bash
pixi run lint
pixi run lint-fix  # auto-fix
pixi run format    # format code
```

### Pre-commit hooks

Pre-commit hooks run automatically on `git commit`. Setup once after cloning:

```bash
pixi run pre-commit-install
```

Run manually on all files:

```bash
pixi run pre-commit-run
```

## Git conventions

See [commit-conventions.md](https://github.com/mattkram/lembas-dev/blob/main/conventions/commit-conventions.md) and [pr-conventions.md](https://github.com/mattkram/lembas-dev/blob/main/conventions/pr-conventions.md).

**Summary:**
- Commits: `<type>: <description>` (feat, fix, docs, refactor, test, chore)
- PRs: Atomic, incremental changes; squash merge via merge queue
- Stack PRs when changes depend on each other

## Architecture

### Core primitives

- **`Case`** — Base class for analysis handlers. Subclass and add `@step` methods.
- **`@step`** — Decorator for execution steps. Supports `requires=` for ordering, `condition=` for skipping.
- **`InputParameter`** — Descriptor for typed inputs with validation (type, min, max, default).
- **`@result`** — Decorator for methods that provide outputs. Lazily evaluated.
- **`CaseList`** — Collection for batch case execution with parameter sweeps.

### Directory layout

```
src/lembas/
  __init__.py      # Public API exports
  case.py          # Case, CaseStep, CaseList, @step
  param.py         # InputParameter descriptor
  results.py       # Results container, @result decorator
  plugins.py       # Plugin registry and discovery
  cli.py           # Typer CLI (lembas command)
  logging.py       # Logger configuration
```

### Plugin system

Plugins register `Case` handlers via entry points:

```toml
# pyproject.toml
[project.entry-points."lembas.plugins"]
reef3d = "lembas_reef3d:Plugin"
```

The CLI discovers plugins at runtime via `pluggy`.

## Design specs

See [lembas-dev](https://github.com/mattkram/lembas-dev) for:
- `lembas.toml` specification
- CLI command design
- Platform integration design
