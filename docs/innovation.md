# Mechanism, hypotheses and scope

## Problem

An application may use 64 source words in a quick preview, then 96/128/192 when more context is allowed. Independently rebuilding each pack can evict earlier evidence even as the budget grows. We plan all configured rungs together for one immutable query/candidate pool. Nesting guarantees that previously emitted source positions survive an increase **within this saved ladder**. It does not guarantee equal answers, stable span IDs, a text prefix, or model KV-cache reuse.

## Existing / borrowed / designed / unverified

- **Established:** BM25 retrieval, greedy budgeted coverage, source overlap merging, incremental/universal selection and beam search. See [literature](literature-review.md) and [prior art](prior-art.md).
- **Borrowed:** diminishing-return coverage intuition, deterministic source coordinates and subset dynamic programming.
- **Designed here:** a finite-grid nested planner that carries cumulative rung utility through overlap-aware beam histories, plus an executable exact subset-DP comparator and a source-hash/offset/cost/nesting verifier. Their combination and measured stability/quality/cost tradeoff are this project's engineering contribution. This does not establish global novelty.
- **Hypotheses, not assumed facts:** joint search helps the coverage proxy compared with irrevocable density-greedy; avoiding evidence eviction need not severely reduce gold-span recall; local planning costs are practical for small candidate pools.
- **Evidence:** refer to the actual records in [experiments](experiments.md). Real-data recall may be worse than an independent selector even when stability is better. Negative findings are retained.

## Formal objective

For candidate intervals C_i, nonnegative scores s_i, and selected indices S, let U(S) be the union of their source-word positions. Distinct document IDs define distinct positions, even when their text matches.

```
w_i = s_i / sum_j s_j           (all zero scores => all zero weights)
cost(S) = |U(S)|
F(S) = sum_i w_i * |U(S) ∩ C_i| / |C_i|
maximize sum_{l=1..L} F(S_l)
subject to S_1 ⊆ ... ⊆ S_L and cost(S_l) <= B_l
```

F is weighted coverage of source positions: each unique source word has a fixed nonnegative aggregate weight. It is monotone submodular as a function of selected candidates. The union cost is also nonadditive. Candidate scores are relevance proxies, not probabilities. Overlapping retrieval windows contribute repeated weight to their shared positions: this is an explicit bias, not independent corroboration.

The objective uses equal weight per configured rung, not continuous integration over budget. Results depend on the whole budget grid. No model-token guarantee, header/prompt overhead guarantee, approximation ratio or downstream QA guarantee is claimed.

## Algorithms

1. Canonicalize by source and candidate IDs; validate intervals and scores.
2. Represent union positions using integer bitsets; cache mask cost and F.
3. For each rung, expand surviving histories by adding one feasible candidate. Keep the best history per current mask; prune each depth and rung to K states using cumulative F, then current F, lower cost and canonical masks to break ties.
4. Backtrack the best final history. Merge touching/overlapping source intervals and emit exact character slices in deterministic source order.
5. Recompute all hashes, costs, slices and nested selections independently from the serialized manifest.

Beam search is approximate. K=1 is a search ablation, not the same algorithm as density greedy. The exact solver enumerates 2^n masks and applies a subset-max transform at each rung, O(L n 2^n) plus coverage evaluation. It is intentionally capped at n=16. Beam expansion explores roughly O(L n² K) proposals, with objective evaluation O(n) per uncached mask and cache memory proportional to explored masks. Worst-case exact complexity remains exponential.

## Falsifiable validation plan (fixed before reading benchmark outcomes)

- H1: every emitted ladder obeys budgets, preserves exact source slices and has zero source-word eviction. One counterexample fails the invariant.
- H2: beam K=16 has a smaller mean exact-objective gap than K=1 and nested density-greedy on 100 generated interval pools (seeds 0–99, n=10). These are algorithmic stress cases, not QA samples.
- H3: on the configured SQuAD dev sample, zero-eviction joint selection offers a useful retention tradeoff against independent density and rank-fill. Report paired gold-span recall differences with article-cluster intervals; do not treat the direction as predetermined or move thresholds after results.
- H4: record planner-only p50/p95 CPU latency and evaluated-mask counts; leave any claim about LLM latency or cloud cost untested.

All selectors receive the same BM25 pool, source-union cost, budgets and coverage proxy. Gold answers are used only after selection. No retraining or model calls are required.
