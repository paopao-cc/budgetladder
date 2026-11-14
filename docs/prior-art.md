# Existing projects and boundaries

Read on 15 November 2026. [research-snapshot.json](research-snapshot.json) records actual GitHub API metadata, HEAD SHAs, licenses and root entries. Dates below describe the observed last push; they do not certify maintenance quality. The implementation here was written independently; no source code from these projects is vendored.

| Project | Function / technical route | Observed code organization | Observed activity / license | Remaining opportunity relative to BudgetLadder |
|---|---|---|---|---|
| [context-knapsack](https://github.com/nradawg/context-knapsack) | Deterministic concept coverage packing, shared token costs, singleton-seeded greedy safeguard and lazy bounds. | TypeScript `src/`, `test/`, package scripts, GitHub workflow. | Last push 2026-08-13; MIT; small repository. | **Closest prior art.** Union/shared costs, coverage and deterministic selection are already implemented. Its documented API returns one pack for one budget; this project studies joint nested packs across a finite budget grid with an exact DP reference. Our independent-density baseline is an independently implemented reference heuristic, not this package. |
| [SlimContext](https://github.com/Yasshu55/SlimContext) | Deterministic post-retrieval deduplication, clustering, MMR and whole-chunk budgeting without LLM calls. | Python `app/`, `benchmarks/`, `tests/`, requirements and pytest config. | Last push 2026-06-07; no license identified by GitHub API at access time; do not copy its code. | CPU context optimization is already common. We focus on retained source intervals across budgets, rather than claiming deterministic dedupe/MMR as novel. |
| [LLMLingua](https://github.com/microsoft/LLMLingua) | Model-based prompt/token compression, LongLLMLingua and LLMLingua-2 implementations. | Python `llmlingua/`, `examples/`, `experiments/`, `tests/`, setup/config files. | Last push 2026-11-09; MIT. | Rich compression capabilities; we target a model-free, exact-source planning component. We have not benchmarked its model methods and claim no superiority. |
| [LangChain](https://github.com/langchain-ai/langchain) | Composable retrievers, document transformers, contextual compression and application integrations. | `libs/` monorepo with package-specific source/tests; separate integration packages. | Last push 2026-11-14; MIT. | A broad integration framework. A small callable budget-ladder planner could be plugged in; we do not replace the framework or suggest that it lacks provenance support generally. |
| [LlamaIndex](https://github.com/run-llama/llama_index) | Node-based retrieval, postprocessors and retrieval/context assembly, including merging approaches. | `llama-index-core/`, `llama-index-integrations/`, docs and development utilities. | Last push 2026-11-14; MIT. | Source/node merging is established; joint finite-grid nesting is the narrower mechanism evaluated here. No claim that merging itself is new. |

## Search scope and novelty risk

We searched RAG context packing, overlapping spans, budget-aware compression and incremental/uncertain-capacity maximization. This is not an exhaustive code or patent search. Similar components can exist elsewhere. The contribution is a **specific independently implemented and experimentally evaluated mechanism**, not a verified first-in-the-world algorithm. The library exposes retriever-independent candidates, so the BM25 demo can be replaced without adopting another framework.

## Candidate directions and weighted decision

Scores 1–5 are engineering judgments, not measurements. Weights: innovation potential .30, usefulness .25, feasibility .20, verifiability .15, open-source adoption .10.

| Candidate | Innovation | Useful | Feasible | Verifiable | Adoption | Weighted |
|---|---:|---:|---:|---:|---:|---:|
| Joint nested source-span budget ladders with auditable manifests | 4 | 4 | 5 | 5 | 4 | **4.35** |
| Query-facet-aware single-budget extractive compression | 3 | 4 | 4 | 4 | 4 | 3.70 |
| Learned confidence calibration for agent memory eviction | 4 | 4 | 2 | 3 | 4 | 3.45 |

The selected direction can be implemented and falsified on a CPU with public source offsets and an exact small-pool reference. The compression direction overlaps heavily with existing tools. Calibration requires a defensible outcome dataset and model inference beyond the current lightweight scope.
