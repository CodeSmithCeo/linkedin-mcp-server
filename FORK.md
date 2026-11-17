# About this fork

This is [CodeSmithCeo](https://github.com/CodeSmithCeo)'s fork of [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server), used by [cv-linkedin-sync](https://github.com/CodeSmithCeo/cv-linkedin-sync) as a git submodule. It is upstream **v4.29.0** plus two local fixes. Everything else is unchanged.

## Divergence from upstream

### Skills section returns only the first ~10 skills

- **Upstream issue:** [stickerdaniel/linkedin-mcp-server#590](https://github.com/stickerdaniel/linkedin-mcp-server/issues/590), "Skills section returns only the top ~10 skills (list truncated)". Open since 2026-07-22, not fixed in v4.29.0.
- **Branch:** `fix/590-skills-wheel-scroll`, based on the `v4.29.0` tag.
- **Cause:** `/details/skills/` has no "Show more" button and does not load more on `window.scrollTo`, which is all the details capture does. It appends the next batch only on a real mouse-wheel event.
- **Fix:** a new `CaptureMode.WHEEL_LOAD` flag, set only for the `skills` section in `linkedin/fields.py`. In `linkedin/capture.py` it wheels at the viewport centre (as the feed already does) until the text in `<main>` stops growing for 3 rounds, capped at 40 rounds. It reads text length only, so it works in any locale.
- **Verified 2026-11-06:** a live read of a profile with 70 skills returned all 70 (10 before the fix).
- **Tests changed:** the expected capture modes in `tests/linkedin/test_person.py`, a scripted answer for the new page read in `tests/linkedin/policy_scenarios.py`, its operation name in `tests/linkedin/support/policy_trace.py`, and the regenerated trace `tests/fixtures/policy-traces/v1/person-sections.json`.

### The profile main page comes back with the top card only

- **Upstream issue:** not filed yet (draft in cv-linkedin-sync, waiting for approval).
- **Branch:** `fix/main-profile-settle`, on top of `fix/590-skills-wheel-scroll`. The submodule points at this branch.
- **Cause:** the main page (`/in/<user>/`) loads in stages. First paint holds the top card and the sidebar only. About, Services, Activity and the other cards arrive later through React Server Component fetches (`/flagship-web/rsc-action/actions/...`). These start about 0.7 s after the load event and finish 2-3 s later. The capture read `<main>` right after navigation. Measured 2026-11-17: 1,505 characters at first paint, 6,170 settled, and the text held still for 1.7 s before the cards arrived, so waiting for the text alone to stop changing is not safe.
- **Why it mostly worked before:** `get_my_profile` navigates to `/in/me/` first. The redirect gave the page time to load before the capture. LinkedIn stopped redirecting `/in/me/` in 11/2026, and a direct read by username exposed the race.
- **Fix:** a new `CaptureMode.SETTLE`, set only for `main_profile` in `linkedin/fields.py`. In `linkedin/capture.py` a `_HydrationTracker` counts the component fetches (listeners on `request`, `requestfinished`, `requestfailed`, installed before navigation like the permalink listener). `_settle` polls every 0.5 s and returns once the text is unchanged and no component fetch is in flight for 1 s. It waits up to 4 s for the first fetch to start, and gives up at 15 s with a warning. Without a tracker (the page was already loaded, `get_my_profile`) it needs 3 s of unchanged text. It counts time in session delay steps, so the wait is deterministic under the fake clock. Text length and URLs only, so it works in any locale.
- **Verified 2026-11-17:** a live `get_person_profile` read of the main page returned 123 lines with About and Activity (15 lines, no About, before the fix).
- **Tests:** `tests/linkedin/test_settle.py` (new: replays the measured timeline, including the 1.7 s trap), the expected capture modes and page events in `tests/linkedin/test_person.py`, scripted settle reads in `tests/linkedin/policy_scenarios.py`, its operation name in `tests/linkedin/support/policy_trace.py`, and the regenerated traces `connect.json`, `get-my-profile.json` and `person-sections.json`.

## Updating to a newer upstream release

1. Check whether #590 and the main page wait are fixed upstream. If both are, drop this fork and point the submodule back at upstream. If one is, drop only that commit.
2. Otherwise rebase both commits onto the new tag: `git fetch upstream --tags && git rebase --onto <new-tag> v4.29.0 fix/main-profile-settle`.
3. Regenerate the traces if they conflict: `uv run python scripts/check_policy_traces.py --output /tmp/traces`, then copy `connect.json`, `get-my-profile.json` and `person-sections.json` over the fixtures.
4. Run `uv run pytest tests/linkedin tests/test_fields.py`, then update this file.
