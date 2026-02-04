# Zwift Training Repo

## Repo intent

- Store Zwift workout files under version control.
- Use a symlink so Zwift reads workouts from this repo.

See `AGENTS.md` for repo rules and operational guidance.

## Layout

- `workouts/`: canonical source of `.zwo` files (one level deep).
- `scripts/`: repo utilities (e.g., `scripts/init-repo.sh`).
- `skills/`: in-repo Codex skills (see below).
- `sub/`: vendored references (git subtree).

## Current state

- Zwift workouts are tracked under `workouts/`.
- The Zwift workout XML reference is vendored as a git subtree under
  `sub/zwift-workout-file-reference`.
- A Codex skill exists at `skills/creating-zwift-workout` to convert plain text
  into `.zwo` files and validate them.

## Setup

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

## Skill usage

Generate a workout from plain text:

```sh
uv run --script skills/creating-zwift-workout/scripts/create_workout.py \
  --text "60 min Z2 + 2–3x2' @ 105–110% of FTP" \
  --name "60min_z2_with_intervals" \
  --output-dir workouts \
  --validate
```

Validate all workouts:

```sh
uv run --script skills/creating-zwift-workout/scripts/validate_zwo.py --path workouts
```

## Subtree notes

This repo vendors the Zwift workout XML reference as a git subtree.

Subtree path:
- `sub/zwift-workout-file-reference`

Upstream:
- https://github.com/h4l/zwift-workout-file-reference.git
- Branch: `master`

Update command:

```sh
git subtree pull --prefix sub/zwift-workout-file-reference https://github.com/h4l/zwift-workout-file-reference.git master --squash
```
