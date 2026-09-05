---
name: quick-fix
description: Use this skill whenever the user directly describes, in their own words (not quoting AI-generated feedback), something they personally noticed while using prompt-generator that they want changed or fixed - a short note like "the X question should default to Y" or "Z is confusing, reword it". Trigger even without an explicit command name; a short first-person observation about the tool's own behavior is enough. Unlike triage-feedback, skip the fix/no-fix sorting - the user has already decided this is worth fixing - and go straight to Issue creation, implementation, commit, and push.
---

# Turn a user note into a shipped fix

The user has already used this generator, noticed something they want changed, and written a short note about it. Unlike AI-relayed feedback (see the `triage-feedback` skill), there is no batch of mixed-quality points to sort - the user has done that judgment call themselves by writing the note. Don't re-litigate whether it's worth fixing.

## Steps

1. **Read the note and make sure you understand the concrete change.** If it's already specific enough to act on, don't stop to confirm - that just adds friction the user explicitly wanted to avoid. Only ask first if the note is genuinely ambiguous (e.g. it could reasonably mean two different changes, or names a question/file that doesn't obviously exist).
2. **Follow `CLAUDE.md`'s workflow end to end**: create a GitHub Issue describing the change, create a `#<Issue番号>` branch, implement it, verify it actually works (monkeypatch `menu.select`/`menu.ask_text` in a throwaway script for interactive flows, or call the relevant function directly, and check the real output), commit, and push. If an Issue for this exact note already exists from earlier in the conversation, reuse it instead of creating a duplicate.
3. **Do not merge.** Report that you pushed, and wait for the user to explicitly say to merge - same as every other change in this repo.
