# ADR 0001: Case Directory Convention

## Status

Accepted

## Context

Engineers need to browse case directories by parameter values. Plugin authors previously
had to implement `case_dir` themselves, leading to inconsistency and boilerplate.

## Decision

### Directory structure

- Default: `cases/{p1}={v1}/{p2}={v2}/{p3}={v3}/`
- Nest first 3 parameters by **declaration order** (good for human browsing)
- Subclasses can override `case_dir` property for full control

### InputParameter additions

- `path_format`: format spec for values in paths (default `.6g` for floats)
- `short_name`: optional alias for shorter directory names

```python
froude_num = InputParameter(
    type=float,
    min=0.2,
    max=3.0,
    path_format=".2f",   # renders as "0.50" not "0.5"
    short_name="Fr",     # renders as "Fr=0.50" not "froude_num=0.50"
)
```

### Case identification

- `case.id` = full SHA-256 of `handler_fqn + ":" + canonical_json(inputs)` (64 hex chars)
- `case.short_id` = first 8 characters of `id` (for display)
- Inputs sorted **alphabetically** for deterministic hashing
- Declaration order for paths, alphabetical for IDs — different concerns

### Index file

- `.lembas/cases.json` maps `id` (full hash) to `{path, handler, all_paths}`
- **Cache only**, not source of truth
- Source of truth: `lembas/case.toml` inside each case directory
- Tracks duplicate paths (same id at multiple locations) via `all_paths`
- Auto-reindexes when stale (disk count differs from indexed count)

### CLI commands

- `lembas cases list`: show cases with status, handler, and notes (duplicates, path mismatches)
- `lembas cases list --pending`: filter to pending cases only
- `lembas cases list --complete`: filter to complete cases only
- `lembas cases reindex`: rebuild index from case.toml files
- `lembas cases clean`: remove stale entries (prompts for confirmation)
- `lembas cases clean --force`: remove stale entries without prompting

## Consequences

- Plugin authors get sensible defaults without boilerplate
- Human-readable directory structure for browsing
- Content-addressed IDs enable platform deduplication
- Index-as-cache pattern tolerates manual directory changes
- Automatic staleness detection keeps index in sync with filesystem
