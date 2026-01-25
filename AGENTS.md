# AGENTS

## Repo intent
- Store Zwift workout files under version control.
- Use a symlink so Zwift reads workouts from this repo.

## Layout
- `workouts/` is the canonical source of `.zwo` files.
- Keep folder depth shallow (one level under `workouts/`).
- Filenames should be ASCII: letters, numbers, `_`, `-` only.

## Setup
- Run `scripts/init-repo.sh` to create the symlink and (optionally) install tooling.
- Zwift only scans workouts on launch; restart after changes.

## Tooling
- Pre-commit hooks are managed by `prek` (Rust-based pre-commit).
- Install hooks with `prek install` after the first setup.
- Run checks manually with `prek run --all-files`.
