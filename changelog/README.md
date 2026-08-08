# Changelog

One file per merged PR, named:

    changelog_dd_mm_yyyy_<author>_<pr-number>.md

Example: `changelog_09_08_2026_irfan_4.md`

Write **user-facing impact** — what changed and why it matters, not a commit dump. A couple of sentences is enough:

    ## What changed
    Added the thermal watchdog to the firmware — the heater now cuts off on its own if the
    temperature goes too high or the laptop stops responding, independent of any command.

    ## Why it matters
    This is the safety mechanism that makes it safe to leave the heater running during the demo.

If a PR gets more commits after it's opened, update its changelog file (and PR description) to match — both should always reflect the PR's current, final scope.
