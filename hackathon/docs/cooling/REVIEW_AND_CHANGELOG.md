# Accepted review and scope of this revision

Revision date: 31 October 2026. Source: Reza's comments supplied by Ali, plus Ali's accepted
user-input/water simplification and supplied KNMI weather files. This is a document/data
instruction update. It does not implement cooling code or integrate the annual plant.

## Reading authority

Read START_HERE in full as the core team/API/layout instruction. Apply current explicit
user instructions and this accepted dated review for the specific amendments below.
DECISIONS holds the active decisions; 01-12 hold their implementation detail. The original
START_HERE snapshot is unchanged, so its older cp=3950, work allocation, branch examples
and 330 wording must not override these accepted changes. Raw challenge/report files are
unchanged references, not silently corrected versions. Preserve public names and meanings.

## Reza's comments mapped to instructions

| Review point | Accepted action | Canonical detail/check |
| --- | --- | --- |
| Annual model/economics/search already exist | Components/evaluator replace placeholders through existing hooks; no new dispatcher; M5 joint and deferred | 01, 02, 04, 07; PROJECT_STATE |
| Deadline 3–4 November | M0, required M1 foundations, M2, minimum tower support, M4 and cooling M6 now; free cooling/maps optional; no new Sensitivity runner | 07 milestone gates; 06 handoff |
| 330 days | Cap actual on-days at 330, mode default at_most; no forced summer running | D004; 04; 08 |
| Brine cp | One Rules value/source, 3990 J/kg/K; historical fixture remains unchanged | D009; 02; 08 current hand checks |
| Temperature/depth | Reservoir T=12+30*depth_km; adapter handles hydrostatics and per-flow/depth loss | 01; 04 |
| Adapter update | Consume wellhead_c and diagnostic well_loss_k once; include 100 m3/h point and approximate deeper-loss check | D001; 04; 08 |
| Candidate/sensitivity speed | Shared vector path over daily/hourly arrays, or scalar day under 20 microseconds; benchmark numerical work separately | 02; 07; 08 |
| Codex/product boundary | No commercial-model calls in runtime; no global runtime configuration or numerical-kernel I/O; AGENTS can be committed | AGENTS; 07 |
| EUR cost handoff | Installed scopes, O&M/life/water/auxiliary/refrigerant records in EUR-2025, r=5.2% real, source/price year retained | 05; 12 |
| Conversion conventions | DEA x1.168 only for applicable 2020 data; Eurostat FX, CEPCI for Towler & Sinnott; inspect actual cost_sources ref | 12; source register |
| Emissions and heat allocation | Plant grid/gas factors 0.20/0.202; no full-plant heat price; shared costs by brine heat used | 05; 12 |
| Small accounting items | chill mechanical, free additive, recovery_hp retained; boiler-first produced gas then flare incl native CO2; auxiliaries once in chillers/towers | 02; 05 |
| Branches/handoffs | ali/cooling-<topic> from main, frequent pushes, draft PRs to main, Reza reviews/merges, PROJECT_STATE current | AGENTS; 07; PROJECT_STATE |
| Ali's weather request | Bundle original hourly/daily weather and provenance; use hourly calculations, daily screening/checking; preserve source/demand calendars | 10; 08 |
| Ali's water simplification | Effective treatment assumed, detailed chemistry excluded; six user inputs plus water balance and physical limits | 11; 03; 05; 08 |

The exact integration branch/ref and the contents of cost_sources.md were not available to
this revision. Reza's supplied statements are accepted team instructions, not a claim
that his current branch code or every economic attribution was independently inspected.
That source lookup is an M0 handoff item, not a reason to create another annual model.

## Preservation and changes

The original START_HERE, historical BENCHMARKS, generic debugging rules (09), challenge PDF,
both original demand CSVs and original design-report PDF are preserved byte-for-byte.
Other existing MD files receive targeted changes only for the accepted scope, defaults,
data/configuration, performance, accounting, verification and continuity updates. Equations,
interface names and unrelated explanatory sections are retained. No original file is removed.

Added canonical instructions are 10_WEATHER_INPUTS, 11_WATER_INPUTS, 12_COST_DATA_HANDOFF and
this review/change record. The complete supplied weather pack is copied unchanged into
the weather raw-data folder, including its provenance files and original source archive.
The challenge-folder demands remain authoritative over duplicate provenance copies.

PACK_VALIDATION.json records actual file/section preservation, links, hashes, calendar and
inventory hand checks. The root MANIFEST covers all current deliverables except itself.
Document checks do not establish cooling-code correctness, performance, sourced installed
EUR prices or a completed joint M5 integration. Preserve live PROJECT_STATE progress when
applying these instructions to a repository where implementation has already started.
