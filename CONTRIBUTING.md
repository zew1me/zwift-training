# Contributing

This repo is intentionally simple: `.zwo` files live in `workouts/`, and we use a small compiler + validator to keep them correct.

If you haven’t already, read `AGENTS.md` first — especially the naming/layout rules.

## Adding or updating a workout

### Rules (please follow these)

- Put `.zwo` files directly under `workouts/` (one level deep).
- Use ASCII filenames: letters, numbers, `_`, `-` only.
- Prefer short, scan-friendly names that describe the main work (intervals/intensity/total time).

### Recommended workflow

1) Create (or edit) a YAML plan under `workout-plans/`.
2) Compile the YAML to a `.zwo` in `workouts/`.
3) Validate the output (and ideally the whole `workouts/` folder).
4) Restart Zwift so it re-scans workouts on launch.

Compile + validate a single plan:

```sh
uv run --script skills/creating-zwift-workout/scripts/compile_workout.py \
  --plan workout-plans/<plan>.yaml \
  --output workouts \
  --validate
```

Validate everything:

```sh
uv run --script skills/creating-zwift-workout/scripts/validate_zwo.py --path workouts
```

## Using Codex (optional, but the point)

When using Codex (Desktop or CLI), ask it to use the in-repo skill:

- Skill: `skills/creating-zwift-workout/SKILL.md`
- Output: YAML plan in `workout-plans/`, compiled `.zwo` in `workouts/`
- Always run validation after generating/edits

## Pre-commit checks (optional but recommended)

This repo uses `prek` for pre-commit hooks.

```sh
prek install
prek run --all-files
```

## Updating the subtree reference (maintainers)

The Zwift workout XML reference is vendored as a git subtree at:

- `sub/zwift-workout-file-reference`

Upstream:

- https://github.com/h4l/zwift-workout-file-reference.git (branch `master`)

Update:

```sh
git subtree pull --prefix sub/zwift-workout-file-reference https://github.com/h4l/zwift-workout-file-reference.git master --squash
```

