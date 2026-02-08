---
name: creating-zwift-workout
description: Convert plain-text workout descriptions into Zwift .zwo files in the repo's workouts/ folder, using the standard warmup and strict validation based on the subtree Zwift workout reference. Use when the user asks to create, generate, or convert text into Zwift workouts, or when they want a validated .zwo output from a short description.
---

# Creating Zwift Workout

This skill should do the heavy lifting in **structured YAML**, then use a thin compiler
script to produce `.zwo` XML and validate it.

## Workflow

1) Convert the user's plain text into a YAML workout plan (schema below).
2) Compile the YAML into `.zwo`.
3) Validate the `.zwo` against the subtree reference.

Note: Run the compiler/validator via `uv run --script` (not `python ...`) so dependencies and shebangs resolve consistently.

```sh
uv run --script skills/creating-zwift-workout/scripts/compile_workout.py \
  --plan skills/creating-zwift-workout/references/example-workout.yaml \
  --output workouts \
  --validate
```

```sh
uv run --script skills/creating-zwift-workout/scripts/validate_zwo.py --path workouts
```

## YAML plan schema

Top-level keys:

Naming convention:
- Prefer a short, scan-friendly `name` that *leads with the main intervals*, then recovery, then intensity, then total time.
- Keep it ASCII and filename-safe (use `_` and `-`), since it becomes the `.zwo` filename via slugify.
- Example: `4x2_3rest_110-120pct_60min`

```yaml
name: "60min Z2 + 3x2 @ 105-110%"
author: "N.Stuke"
description: "60 min Z2 + 3x2' @ 105–110% of FTP"
sport: "bike"  # default: bike
ftp: 260       # only needed when using watts
tags: ["CUSTOM"]
blocks:
  - type: standard_warmup
  - type: steady
    minutes: 30
    power: z2
  - type: intervals
    repeat: 3
    on_minutes: 2
    on_power: [1.05, 1.10]
    off_minutes: 2
    off_power: 0.5
  - type: cooldown
    minutes: 10
```

### Block types (supported)

- `standard_warmup`: expands to the repo's common warmup sequence.
- `warmup`, `cooldown`: duration + `power_low`/`power_high`.
- `steady`: duration + `power`.
- `ramp`: duration + `power_low`/`power_high`.
- `freeride`: duration, optional cadence.
- `intervals`: `repeat`, `on_minutes`, `off_minutes`, `on_power`, `off_power`, optional `cadence`, `cadence_rest`.
- `maxeffort`: duration.
- `textevent`: `time_offset` (seconds) + `message`.
- `repeat`: a control block with `times` + `blocks` (see DSL below).

### Power fields

Power fields accept:

- a float (0.65 => 65% FTP)
- a zone string (z1..z6)
- a range `[low, high]` (used as PowerLow/PowerHigh)
- a dict: `{pct: 110}` or `{watts: 250}` (requires `ftp`)

### DSL: repeat blocks

Use `repeat` to loop over multiple blocks:

```yaml
- type: repeat
  times: 2
  blocks:
    - type: intervals
      repeat: 4
      on_minutes: 2
      on_power: {pct: 105}
      off_minutes: 3
      off_power: 0.5
    - type: steady
      minutes: 8
      power: 0.5
```

## Parsing rules

- Ask clarifying questions only when required for correctness (e.g., watts without FTP).
- If the user omits optional details (cadence, rest cadence, power ranges), omit those attributes.
- Intervals should generally be placed near the end, but preserve explicit ordering in the YAML.
- Always include a cooldown of at least 5 minutes unless the user explicitly removes it.

## References

See `references/zwift-schema.md` for the subtree schema inputs used by the validator.
