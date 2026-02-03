---
name: creating-zwift-workout
description: Convert plain-text workout descriptions into Zwift .zwo files in the repo's workouts/ folder, using the standard warmup and strict validation based on the subtree Zwift workout reference. Use when the user asks to create, generate, or convert text into Zwift workouts, or when they want a validated .zwo output from a short description.
---

# Creating Zwift Workout

Use the scripts in `scripts/` to generate and validate workouts.

## Workflow

1) Generate a workout from text:

```sh
uv run --script skills/creating-zwift-workout/scripts/create_workout.py \
  --text "2x [4x2' 3' RBI] 8' RBS , 60 min total, 10 minute cooldown after interval." \
  --name "2x4x2" \
  --output-dir workouts \
  --validate
```

2) Validate existing workouts:

```sh
uv run --script skills/creating-zwift-workout/scripts/validate_zwo.py --path workouts
```

## Parsing rules

- Intervals are placed near the end, with a cooldown of at least 5 minutes.
- A standard warmup is always inserted (ramp + high-cadence spin-ups).
- If a total duration is provided, the base steady block fills the remaining time.
- If watt-based intervals are provided, the text must include FTP (e.g., "FTP 260").
- Interval ranges like "2–3x" use the upper bound.
- Power ranges like "105–110%" are encoded as PowerOnLow/PowerOnHigh (or Off equivalents); single values use OnPower/OffPower.
- Optional cadence hints like "cadence 95" or "rest cadence 85" map to Cadence/CadenceResting on IntervalsT.
- If the user omits optional details (cadence, resting cadence, power ranges), do not block generation; omit those attributes.
- If the user omits required details for correctness (e.g., FTP for watt-based targets), ask a clarifying question.

## References

See `references/zwift-schema.md` for the subtree schema inputs used by the validator.
