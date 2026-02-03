# Zwift schema reference (subtree)

Authoritative reference files in this repo (git subtree):

- `sub/zwift-workout-file-reference/tag_attr_usage.json`
- `sub/zwift-workout-file-reference/descriptions.yaml`
- `sub/zwift-workout-file-reference/zwift_workout_file_tag_reference.md`

Validator strategy:
- Use `tag_attr_usage.json` for the canonical element and per-tag attribute allowlist.
- Use `descriptions.yaml` to expand the global allowlist (tags/attrs that appear in docs).

When adding new tags/attrs, update the validator logic if needed and re-run validation on `workouts/*.zwo`.
