# 7-Day Plan — Omniscol Translation Pipeline V2

Written from where things actually stand: the core architecture (normalize →
glossary → classify → batch → prompt → structural validation → semantic
validation → export) is built and unit-tested, and has already found 4 real
bugs in the live Polish translation file. What's left is verification against
a live model, glossary expansion, and writing this up so it's defensible.

This plan does not invent a fake multi-week history. It's a forward plan
for the days you actually have.

## Day 1 (today/tomorrow) — Verify and understand what exists
- Read through `src/` end to end — every module is short and commented;
  you need to be able to explain each one, not just paste it
- Run `pytest tests/ -v` and `audit-v2` yourself, confirm you get the same
  4 collisions on real `pl_webapp.json`
- Decide: do you have live Vertex AI/Gemini access working right now
  (same as V1 used)? If yes, do step 2 below today instead of Day 2.

## Day 2 — Live LLM verification
- Run `generate-v2 --lang <code> --module login --live` against a language
  with a few genuinely missing keys (or temporarily remove some from a
  copy of an existing file, the way the test harness does)
- Compare output against `MockLLMClient` output to confirm the real prompt
  produces sane translations and the LLM review pass returns something
  useful (not empty, not garbage)
- Fix anything that breaks — this is the one part of the pipeline not
  already proven working

## Day 3 — Fix the known false-positive issue + expand glossary
- Restrict the stage-8 "expected concept term" check so it only applies to
  bare/near-bare canonical keys (e.g. `class`, `class.name`) rather than
  every leaf key under a namespace (e.g. every individual `absence.reason.*`
  value) — this removes ~200 noisy REVIEW flags that aren't real issues
- Expand `config/concepts.json` beyond the 17 seeded concepts by walking
  through the remaining webapp namespaces (`admin`, `diagnose`, `error`,
  `staffing`, `wishes`, `level`, `course`) and the full `Glossary.md`

## Day 4 — Run audit-v2 across every existing language file
- `pl`, `ml`, `it`, `es`, `de`, `nl`, `kz`, `ar`, `he`, `zh`, `pt`, `ru`, `vi`
- Collect every ERROR-level (not REVIEW) finding — these are the ones worth
  bringing to your supervisor as concrete evidence of value
- This produces the strongest section of your write-up: a table of real
  concept-confusion bugs found across languages, with before/after

## Day 5 — Sync integration
- Point V1's `sync-missing-keys` command at the V2 pipeline instead of the
  flat 200-key chunker, so new keys get semantic batching + validation by
  default going forward
- Keep V1's command working unchanged for languages you haven't re-audited,
  so nothing regresses

## Day 6 — Documentation and write-up
- Update this into a short "V2 progress report" section (or a supplement to
  the AI Clinic report) covering: what changed, why, the real bugs found,
  what's still mock-only, what's next
- Make sure every claim in the report matches something you can point to in
  code or test output if your lead asks

## Day 7 — Buffer + supervisor conversation
- Buffer day for whatever slipped
- Prepare a 5-minute walkthrough: show `audit-v2` output live, show the
  test suite passing, be upfront about what's mock-only

## What to say if asked directly about the gap in communication
Be straightforward: you went quiet for a couple of months, and this is the
work that's been done to catch back up, built on the real architecture your
lead asked for rather than a quick patch. The four real bugs found in the
first day of work are concrete, verifiable evidence the new approach adds
value beyond V1 — lead with that rather than apologizing at length.
