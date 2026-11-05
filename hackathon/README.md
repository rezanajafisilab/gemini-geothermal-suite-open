# hackathon/: Dioscuri's evidence, notes and tools

Material that supports Dioscuri but is not part of GEMINI. The app reads some of it at run time
(the GEMINI patches, the evaluation runs shown in the Evidence tab, the notes its document search
reads), so keep the layout.

| Path | What |
|---|---|
| [gemini_bughunt/](gemini_bughunt/) | The 10 GEMINI issues: write-up, reproduction scripts, outputs and one patch per issue (applied at run time by `src/gemini_agent/gemini_runtime.py`) |
| [evals/](evals/) | Evaluation scenarios (`scenarios/`: chat, unclear requests, conversations), the runner (`run_evals.py`), model benchmarks (`BENCHMARKS.md`) and recorded runs with tokens and times (`runs/`) |
| [docs/decisions/](docs/decisions/) | Architecture decision records, ADR-0002 to ADR-0018 |
| [docs/calculation_audit/](docs/calculation_audit/) | The audit of the physics, finance and reliability calculations, with its scripts |
| [docs/cooling/](docs/cooling/), [docs/cooling_design.md](docs/cooling_design.md) | The cooling model: scope, equations, dispatch, costs, verification |
| [docs/reliability.md](docs/reliability.md) | Outages, N-1 and risk |
| [docs/challenge/cost_sources.md](docs/challenge/cost_sources.md), [research/](research/) | Where the cost and plant numbers come from |
| [docs/caught_and_fixed.md](docs/caught_and_fixed.md) | Mistakes caught and fixed, as listed in the Evidence tab |
| [reviews/](reviews/) | Two review panels (31 Oct, 1 Nov) and a challenge review (1 Nov): reviewer agents, one per role, used the running app and read the code; the caught-and-fixed list cites them |
| [docs/workbench_api.md](docs/workbench_api.md) | The server's API for the interface's tabs |
| [scripts/](scripts/) | Builders: the release zip (`make_release.py`), the real projects, the weather inputs, benchmarks |
| [brand/](brand/) | The Dioscuri logo |
| `data/` | Local data folders (empty in the repository) |
| `requirements-dev.txt` | Test and lint tools |
