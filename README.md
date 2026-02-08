# Zwift Training Repo

Do you want to create your own Zwift workouts, but feel like it’s cumbersome to do so in the UI creator tool? Would you rather create it just by chatting? Now you can, using Codex.

This repo is set up so you can:

- Generate workouts by describing them in plain English (via Codex).
- Compile + validate them into real `.zwo` files (so Zwift will actually import them).
- Keep everything in git, so you can iterate, diff, share, and roll back.
- Symlink Zwift’s workouts folder to `workouts/` so changes show up in-game after a restart.

See `AGENTS.md` for repo rules (naming, layout, etc.).

## Layout

- `workouts/`: canonical source of `.zwo` files (one level deep).
- `workout-plans/`: YAML workout plans used to generate `.zwo` files.
- `scripts/`: repo utilities (e.g., `scripts/init-repo.sh`).
- `skills/`: the Codex skill used to generate + validate workouts.
- `sub/`: vendored references (git subtree) used by the validator.

## Getting started

### 1) Clone the repo

```sh
git clone <this-repo-url>
cd zwift-training
```

### 2) Install Codex (Desktop or CLI)

Pick one:

- Codex Desktop: install and open this repo folder (see https://openai.com/codex/get-started)
- Codex CLI: install + run it from this repo:

  ```sh
  npm install -g @openai/codex
  codex
  ```

  Docs: https://developers.openai.com/codex/cli

### 3) Install `uv` (for the workout compiler/validator)

The workout generator scripts are run via `uv run --script ...` (see examples below).

Install `uv`: https://docs.astral.sh/uv/

### 4) Link Zwift to this repo (symlink)

Run the symlink initializer (backs up your Zwift user folder, imports `.zwo`
files into `workouts/`, and replaces the user id folder with a symlink to the
repo workouts directory by default):

```sh
scripts/init-repo.sh
```

Restart Zwift after changes; it only scans workouts on launch.

If you prefer the legacy `custom/` subfolder link, use:

```sh
scripts/init-repo.sh --link-custom
```

## Using Codex to create workouts (recommended)

Open this repo in Codex (Desktop) or run Codex CLI from the repo root. Then ask for what you want in plain English, and tell it to use the in-repo skill:

> Use the `creating-zwift-workout` skill in `skills/creating-zwift-workout/SKILL.md`.
> Create a YAML plan under `workout-plans/`, compile it to `workouts/`, and validate it.

Example prompt:

> Create a 60-minute workout: 30' Z2, then 4x2' @ 110–120% FTP with 2' easy between, then 10' cooldown. Name it `60min_z2_4x2_110-120pct`.

After Codex generates the files, restart Zwift so it re-scans workouts.

## Creating workouts without Codex (manual)

Create a YAML plan (example: `workout-plans/60min_z2_4x2_110-120pct.yaml`), then compile + validate:

```sh
uv run --script skills/creating-zwift-workout/scripts/compile_workout.py \
  --plan workout-plans/60min_z2_4x2_110-120pct.yaml \
  --output workouts \
  --validate
```

Validate everything under `workouts/`:

```sh
uv run --script skills/creating-zwift-workout/scripts/validate_zwo.py --path workouts
```

## Contributing / making changes

See `CONTRIBUTING.md` for the “how we do changes here” workflow (naming rules, validation, pre-commit checks, subtree updates).
