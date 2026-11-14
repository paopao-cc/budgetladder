"""Nested beam search and small-pool exact dynamic programming.

Beam search has no approximation guarantee. Exact mode is an executable oracle
for the SAME nested objective, not an oracle for answer preservation.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
from .model import EvidenceProblem, Pack


def _budgets(budgets: Iterable[int]) -> tuple[int, ...]:
    bs = tuple(budgets)
    if not bs or any(type(b) is not int or b < 0 for b in bs):
        raise ValueError("provide nonnegative integer budgets")
    if any(a >= b for a, b in zip(bs, bs[1:])):
        raise ValueError("budgets must be strictly increasing")
    return bs


@dataclass(frozen=True)
class _State:
    mask: int
    value: float
    path: tuple[int, ...]


def _key(problem: EvidenceProblem, state: _State) -> tuple:
    cost, utility, _ = problem.metrics(state.mask)
    return (state.value, utility, -cost, -state.mask, tuple(-m for m in state.path))


def plan_ladder(problem: EvidenceProblem, budgets: Iterable[int], *, beam_width: int = 24) -> tuple[Pack, ...]:
    """Maximize sum of rung utilities approximately, subject to nested sets.

    At each rung, propagate histories by single-candidate additions. Keep the
    best history for each mask; prune each expansion depth and completed rung
    to beam_width states. Empty/stalled rungs are valid. Canonical IDs break ties.
    The full budget grid is part of the input: changing it can change the plan.
    """
    bs = _budgets(budgets)
    if type(beam_width) is not int or beam_width < 1:
        raise ValueError("beam_width must be a positive integer")
    beam = [_State(0, 0.0, ())]
    n = len(problem.candidates)
    for budget in bs:
        # value includes the current utility once, independent of addition count.
        archive = {s.mask: _State(s.mask, s.value + problem.metrics(s.mask)[1], s.path + (s.mask,)) for s in beam}
        frontier = list(archive.values())
        for _ in range(n):
            proposals: dict[int, _State] = {}
            for state in frontier:
                previous_value = state.value - problem.metrics(state.mask)[1]
                for i in range(n):
                    mask = state.mask | (1 << i)
                    if mask == state.mask or problem.metrics(mask)[0] > budget:
                        continue
                    new = _State(mask, previous_value + problem.metrics(mask)[1], state.path[:-1] + (mask,))
                    old = archive.get(mask)
                    if old is None or _key(problem, new) > _key(problem, old):
                        archive[mask] = new
                        proposals[mask] = new
            if not proposals:
                break
            frontier = sorted(proposals.values(), key=lambda s: _key(problem, s), reverse=True)[:beam_width]
        beam = sorted(archive.values(), key=lambda s: _key(problem, s), reverse=True)[:beam_width]
    best = max(beam, key=lambda s: _key(problem, s))
    return tuple(problem.pack(m, b) for m, b in zip(best.path, bs))


def exact_ladder(problem: EvidenceProblem, budgets: Iterable[int]) -> tuple[Pack, ...]:
    """Exact nested objective via subset-max DP: O(L n 2**n), n <= 16."""
    bs = _budgets(budgets)
    n = len(problem.candidates)
    if n > 16:
        raise ValueError("exact mode is limited to 16 candidates")
    count = 1 << n
    states: list[_State | None] = [None] * count
    states[0] = _State(0, 0.0, ())
    for budget in bs:
        # Subset transform: best predecessor P subseteq M for every M.
        best = states.copy()
        for i in range(n):
            for m in range(count):
                if m & (1 << i):
                    other = best[m ^ (1 << i)]
                    if other is not None and (best[m] is None or _key(problem, other) > _key(problem, best[m])):
                        best[m] = other
        states = [None] * count
        for m, pred in enumerate(best):
            cost, utility, _ = problem.metrics(m)
            if pred is not None and cost <= budget:
                states[m] = _State(m, pred.value + utility, pred.path + (m,))
    winner = max((s for s in states if s is not None), key=lambda s: _key(problem, s))
    return tuple(problem.pack(m, b) for m, b in zip(winner.path, bs))


def _greedy(problem: EvidenceProblem, budget: int, initial: int = 0) -> int:
    mask = initial
    while True:
        cost, utility, _ = problem.metrics(mask)
        choices = []
        for i, c in enumerate(problem.candidates):
            new = mask | (1 << i)
            if new == mask:
                continue
            new_cost, new_utility, _ = problem.metrics(new)
            gain = new_utility - utility
            if new_cost <= budget and gain > 1e-12:
                choices.append((gain / max(1, new_cost - cost), gain, c.score, -i, new))
        if not choices:
            return mask
        mask = max(choices)[-1]


def independent_greedy(problem: EvidenceProblem, budgets: Iterable[int]) -> tuple[Pack, ...]:
    """Independent marginal density with a best-singleton-seeded safeguard.

    Both starts are greedily filled; better final utility wins at each budget.
    This is a strong reference heuristic, not the external context-knapsack code.
    """
    result = []
    for budget in _budgets(budgets):
        starts = [0] + [1 << i for i in range(len(problem.candidates))
                        if problem.metrics(1 << i)[0] <= budget]
        singleton = max(starts, key=lambda m: (problem.metrics(m)[1], -m))
        masks = [_greedy(problem, budget), _greedy(problem, budget, singleton)]
        mask = max(masks, key=lambda m: (problem.metrics(m)[1], -problem.metrics(m)[0], -m))
        result.append(problem.pack(mask, budget))
    return tuple(result)


def nested_greedy(problem: EvidenceProblem, budgets: Iterable[int]) -> tuple[Pack, ...]:
    """Ablation: irrevocable density additions, no joint beam histories."""
    mask = 0
    result = []
    for budget in _budgets(budgets):
        mask = _greedy(problem, budget, mask)
        result.append(problem.pack(mask, budget))
    return tuple(result)


def ranked_fill(problem: EvidenceProblem, budgets: Iterable[int]) -> tuple[Pack, ...]:
    """Score-descending skip-if-does-not-fit, with the SAME overlap union cost."""
    order = sorted(range(len(problem.candidates)), key=lambda i: (-problem.candidates[i].score, problem.candidates[i].id))
    result = []
    for budget in _budgets(budgets):
        mask = 0
        for i in order:
            if problem.metrics(mask | (1 << i))[0] <= budget:
                mask |= 1 << i
        result.append(problem.pack(mask, budget))
    return tuple(result)


def nested_rank_fill(problem: EvidenceProblem, budgets: Iterable[int]) -> tuple[Pack, ...]:
    """Strong simple stability reference: retain old IDs, then score-fill each rung."""
    order = sorted(range(len(problem.candidates)), key=lambda i: (-problem.candidates[i].score, problem.candidates[i].id))
    result = []
    mask = 0
    for budget in _budgets(budgets):
        for i in order:
            if problem.metrics(mask | (1 << i))[0] <= budget:
                mask |= 1 << i
        result.append(problem.pack(mask, budget))
    return tuple(result)
