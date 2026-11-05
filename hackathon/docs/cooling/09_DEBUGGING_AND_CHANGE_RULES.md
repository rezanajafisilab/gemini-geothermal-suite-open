# 09. Debugging, changes and continuity

## Before a behaviour change

Read the routing table, then the relevant specification, DECISIONS, current implementation,
callers and verification cases. Identify the failing requirement or intended new behaviour.
Write a short plan with affected units, fields, boundary and evidence. Preserve working
unrelated changes. Routine configurable assumptions do not require repeatedly asking Ali;
record them. Breaking a frozen public name requires the agreement specified in START_HERE.

## Debug one operating point first

Capture date, scenario/config ID, per-well flow and wellhead temperature, hot/chilled/sink
inlets and flows, equipment mode/capacity/PLR, allocated heat, each power, all outlets/dp,
energy residual and iteration trace. Include provider/version and source IDs. Solve a failing
day/component before rerunning a whole optimization. Diagnostics are returned data; printing
and file/network access stay in a CLI/report layer outside pure functions.

Use stable diagnostic codes (e.g. ABS_HOT_LIMIT, SINK_CAPACITY, WELL_FLOW_CAP,
RETURN_NOT_VALIDATED, SOLVER_NONCONVERGED) plus START_HERE's dated plain-language violations.
State the observed value, allowed limit and consequence. Missing calibration is a data-quality
status; a genuine exceeded operating limit is a constraint violation. Keep both visible.

## Fix and review

Add an independent regression for a meaningful physics/accounting bug, fix the smallest
responsible layer, then run the relevant checks. A refactor must preserve observable API and
units. Do not make a test pass by changing demand, widening hard caps, removing a failed
scenario or clipping bad physics. Do not silently replace a high-grade temperature budget
with total geothermal heat. Reconcile summaries to detailed inventories after any change.

Update the canonical MD section if implemented behaviour changes. Record a stable decision
ID with rationale/source, old and new behaviour, affected tests and whether historical
benchmarks remain applicable. Do not copy all specifications into a second competing file.

## End-of-change / handoff checklist

- Relevant checks run and outcome recorded, including skipped/failed checks.
- Affected specification and assumption/source entries updated.
- PROJECT_STATE has current branch/commit if known, milestone, changed files, last actual
  checks, unresolved blockers, exact next action and current completion limits.
- Any breaking-interface proposal is separated from an implemented migration.
- No 'done' label based only on a report example, stub or an unexecuted test command.

Keep PROJECT_STATE short and replace stale current-status entries. Preserve rationale/history
in DECISIONS, not a growing diary in every file. At a new run or after compaction, reopen
the initial reading set and use state to resume; verify it against the repository.

If a source changes, compare versions/hashes and evaluate affected equations, defaults,
fixtures and outputs. Update the register after review, never just to silence a mismatch.
If AGENTS changes, a fresh Codex run rebuilds discovery; explicitly reread changed linked
MD files in the current session. An override/nested file may affect the active instruction
chain. Inspect it rather than deleting other project guidance.
