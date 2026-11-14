# Experiments and honest findings

Executed 15 November 2026, Darwin arm64, Python 3.15.0. No GPU or model/API calls. This release evaluates a context planner, not an end-to-end answer-generating system.

## Data, protocol and leakage boundaries

- Official SQuAD 1.1 development JSON; SHA-256 `95aa6a52d5d6a735563366753ca50492a658031da74f301ac5238b03966972c9`; 10,570 available questions; 0 inconsistent gold annotations filtered.
- Index **all 2,067 paragraphs** before sampling questions; 6,870 fixed windows (64 source words, 32 overlap). One original paragraph is one document. Gold paragraph IDs are not given to the planner.
- Python `Random(2026).shuffle` over questions in dataset order; first 300 questions, 47 articles. This is an exploratory subset of the public dev set, not a held-out test-set claim.
- Same top-16 BM25 candidates, scores, source-union costs and budgets [64, 96, 128, 192] for every method. No answer labels used in retrieval, utility or planning.
- Main config, objective and sample were fixed before viewing outcomes. **Nested score fill was added after the initial negative beam result** to test a stronger simple zero-eviction comparator. This is disclosed rather than presented as preregistration. No parameters were retuned to improve measured recall.
- Gold-span hit requires one emitted source slice in the correct paragraph to contain the full character interval of at least one annotated answer. Matching answer strings in distractors does not count. Merged adjacent windows can jointly cover an answer.
- Candidate-pool recall is **91.33%**; this is the attainable ceiling for this pool, not perfect retrieval.

## Real-data results

Mean rung recall averages 4 binary hits for each of 300 questions. Adjacent-rung transitions total 900 per method. Source-word eviction is the fraction of old source positions missing from the next rung, averaged across those transitions, counting an empty prior pack as zero.

| Method | Mean rung answer-span recall ↑ | Answer-loss transitions ↓ | Mean source-word eviction ↓ | Planner p50 (ms) ↓ |
|---|---:|---:|---:|---:|
| Independent score fill | 76.83% | 3 | 4.65% | 0.138 |
| Nested score fill | 76.58% | 0 | 0.00% | 0.139 |
| Independent density + seed | 64.25% | 24 | 11.24% | 0.260 |
| Nested density greedy | 58.08% | 0 | 0.00% | 0.173 |
| Joint beam, K=1 | 63.58% | 0 | 0.00% | 0.207 |
| Joint beam, K=16 | 62.17% | 0 | 0.00% | 1.468 |

| Method | Recall @64 | @96 | @128 | @192 | Mean coverage utility | Planner p95 (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Independent score fill | 70.67% | 74.33% | 79.00% | 83.33% | 0.2499 | 0.202 |
| Nested score fill | 70.67% | 74.33% | 77.00% | 84.33% | 0.2468 | 0.207 |
| Independent density + seed | 55.33% | 60.00% | 67.00% | 74.67% | 0.2703 | 0.372 |
| Nested density greedy | 48.00% | 54.33% | 58.00% | 72.00% | 0.2570 | 0.235 |
| Joint beam, K=1 | 55.33% | 61.00% | 63.33% | 74.67% | 0.2575 | 0.284 |
| Joint beam, K=16 | 53.67% | 57.00% | 64.33% | 73.67% | 0.2684 | 1.800 |

**Interpretation:** nesting guarantees no evidence removal for either nested score fill or the experimental beam method. Joint beam beats nested density greedy on the measured proxy and mean gold-span recall, but simple nested score fill is much better on gold-span recall and faster. Wider beam improves the proxy over beam K=1 while lowering answer retention. H1 and H2 are supported in the executed checks. H3 does not support recommending beam for answer preservation over the strongest simple baseline. No SOTA, LLM latency saving, generation quality or cost-saving claim follows.

## Paired uncertainty

Paired differences average each question's four rung hits before comparing methods. Percentile bootstrap samples entire article clusters with replacement, 2,000 replicates, seed 2026; recompute the question-weighted mean in each draw. These exploratory intervals reflect this sampled dev set, are not multiplicity-adjusted, and do not cover domain shift or alternative retrievers.

| Beam K=16 minus comparator | Recall difference (percentage points) | 95% article-cluster percentile interval |
|---|---:|---:|
| Independent density + seed | -2.08 | [-3.36, -0.93] |
| Nested density greedy | +4.08 | [+1.51, +6.66] |
| Nested score fill | -14.42 | [-18.47, -10.22] |
| Independent score fill | -14.67 | [-18.86, -10.22] |

## Exact-reference stress study and ablations

100 independently generated interval pools, seeds 0–99; 3 documents of 60 source words, n=10 candidates, starts in [0,44], lengths 3–15, random nonnegative relevance; budgets [12,24,40]. This is original **synthetic algorithmic testing**, not real QA evidence. All methods optimize the same cumulative coverage proxy; the exact subset-DP reference enforces the same nesting constraint.

| Method | Mean relative gap to exact ↓ | Worst relative gap ↓ | Mean planner ms |
|---|---:|---:|---:|
| Beam K=1 | 7.607% | 36.917% | 0.140 |
| Beam K=16 | 0.057% | 3.711% | 0.762 |
| Nested density greedy | 1.642% | 12.678% | 0.101 |

Beam K=1 ablates search width; nested density greedy ablates joint history retention. The small-pool exact solver is also compared with exhaustive enumeration in unit tests. All real-data selectors receive overlap merging, preventing deduplication alone from explaining an apparent gain. No external library's speed or accuracy is measured by these independently implemented baselines.

## Failure cases

Full coordinate selections and values are in [failure-cases.json](../experiments/results/failure-cases.json), with IDs that can be resolved against the separately downloaded source data.

- **Proxy mismatch**, question `572fc6f204bcaa1900d76cf9`: nested score fill retains the gold span at all four budgets; beam only at 192. Beam's coverage utility is higher at each rung. The measured proxy prefers a different collection of source positions, exposing the objective/answer mismatch.
- **Evidence eviction**, question `56e7550700c9c71400d76fc6`: independent density has hits `[0,1,0,1]`, losing an answer when going from 96 to 128 source words. Beam has `[0,0,0,1]`: stability alone also does not rescue a bad initial choice.
- **Retriever ceiling**, question `5733d68ed058e614000b637f`: the top-16 pool contains no full gold span; all tested planners fail. A packing algorithm cannot reconstruct missing evidence.
- **Useful search gain**, question `5726a2445951b619008f7864`: nested density has `[0,0,0,1]`; beam has `[0,0,1,1]`. Joint search can improve some cases while losing others.

Short final windows have high coverage per word, and overlapping retrieval windows repeatedly weight shared source positions. These are plausible contributors to mismatch, not independently isolated causal findings. A future utility change needs a new evaluation split; we do not tune it on these outcomes.

## Runtime, test and release evidence

CPU planner timings use fresh per-method cost caches; they exclude retrieval, pool construction, audit and file output. Each method runs once per question in fixed order; there is no randomized-order microbenchmark or hardware comparison. Cache masks are recorded per question as a search-size measure; peak process RAM is not measured. No claim about total RAG latency or energy is made.

- **18 unit tests passed** locally, including 100 randomized nested/budget cases, 20 wide-beam/exact comparisons, eight exhaustive nested-chain comparisons, input-order invariance, Unicode/source boundaries, cost accounting and manifest tampering.
- Both beam and nested-rank CLI paths executed; exported manifests independently verified.
- Original demo output is recorded in `assets/demo.txt`, `assets/demo-manifest.json` and the generated GIF.
- The GitHub Actions matrix is a configured check, not proof it has run; consult actual workflow runs.

## Reproduction and records

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python experiments/oracle.py
mkdir -p data
curl -fL --compressed https://rajpurkar.github.io/SQuAD-explorer/dataset/dev-v1.1.json -o data/dev-v1.1.json
python experiments/benchmark.py --data data/dev-v1.1.json --config configs/squad.json
```

- [Frozen config](../configs/squad.json)
- [Real-data summary](../experiments/results/squad/summary.json)
- [Per-question raw records](../experiments/results/squad/records.jsonl)
- [Exact-reference cases](../experiments/results/oracle.json)
- [Failure selections](../experiments/results/failure-cases.json)

Rerunning overwrites the selected output directory; use `--output` for a new real-data run. `oracle.py --output` preserves alternate stress runs. Deterministic selections/metrics should reproduce under the same source/config; timings and final floating-point digits can differ. Dataset text is not shipped; CC BY-SA source terms apply separately from MIT software terms. No external learned-compressor baseline or downstream answer generation was run.
