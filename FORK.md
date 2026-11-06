# About this fork

This is [CodeSmithCeo](https://github.com/CodeSmithCeo)'s fork of [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server), used by [cv-linkedin-sync](https://github.com/CodeSmithCeo/cv-linkedin-sync) as a git submodule. It is upstream **v4.29.0** plus one local fix. Everything else is unchanged.

## Divergence from upstream

### Skills section returns only the first ~10 skills

- **Upstream issue:** [stickerdaniel/linkedin-mcp-server#590](https://github.com/stickerdaniel/linkedin-mcp-server/issues/590), "Skills section returns only the top ~10 skills (list truncated)". Open since 2026-07-22, not fixed in v4.29.0.
- **Branch:** `fix/590-skills-wheel-scroll`, based on the `v4.29.0` tag.
- **Cause:** `/details/skills/` has no "Show more" button and does not load more on `window.scrollTo`, which is all the details capture does. It appends the next batch only on a real mouse-wheel event.
- **Fix:** a new `CaptureMode.WHEEL_LOAD` flag, set only for the `skills` section in `linkedin/fields.py`. In `linkedin/capture.py` it wheels at the viewport centre (as the feed already does) until the text in `<main>` stops growing for 3 rounds, capped at 40 rounds. It reads text length only, so it works in any locale.
- **Verified 2026-11-06:** a live read of a profile with 70 skills returned all 70 (10 before the fix).
- **Tests changed:** the expected capture modes in `tests/linkedin/test_person.py`, a scripted answer for the new page read in `tests/linkedin/policy_scenarios.py`, its operation name in `tests/linkedin/support/policy_trace.py`, and the regenerated trace `tests/fixtures/policy-traces/v1/person-sections.json`.

## Updating to a newer upstream release

1. Check whether #590 is fixed upstream. If it is, drop this fork and point the submodule back at upstream.
2. If not, rebase this branch onto the new tag: `git fetch upstream --tags && git rebase --onto <new-tag> v4.29.0 fix/590-skills-wheel-scroll`.
3. Regenerate the trace if it conflicts: `uv run python scripts/check_policy_traces.py --output /tmp/traces`, then copy `person-sections.json` over the fixture.
4. Run `uv run pytest tests/linkedin tests/test_fields.py`, then update this file.
