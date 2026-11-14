"""Recompute provenance, source hashes, costs, and nesting; fail closed."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
from math import isclose
from typing import Iterable
from .model import Candidate, Document, EvidenceProblem, Pack


def audit_ladder(problem: EvidenceProblem, packs: Iterable[Pack], *, require_nested: bool = True) -> dict:
    ps = tuple(packs)
    if not ps or any(a.budget >= b.budget for a, b in zip(ps, ps[1:])):
        raise ValueError("empty ladder or unordered budgets")
    old_union = 0
    previous_ids: set[str] = set()
    for pack in ps:
        if len(set(pack.selected)) != len(pack.selected):
            raise ValueError("duplicate selected candidate")
        mask = problem.mask(pack.selected)
        expected = problem.pack(mask, pack.budget)
        if expected.cost != pack.cost or expected.spans != pack.spans or not isclose(expected.utility, pack.utility, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("manifest does not match source/cost/utility")
        union = problem.metrics(mask)[2]
        if require_nested and (old_union & ~union or not previous_ids <= set(pack.selected)):
            raise ValueError("evidence was evicted")
        old_union = union
        previous_ids = set(pack.selected)
    return {"rungs": len(ps), "budget_unit": "source_words", "nested": all(set(a.selected) <= set(b.selected) for a, b in zip(ps, ps[1:])), "verified": True}


def export_ladder(problem: EvidenceProblem, packs: Iterable[Pack]) -> dict:
    ps = tuple(packs)
    audit_ladder(problem, ps)
    return {"schema_version": 1, "budget_unit": "source_words", "objective": "weighted_source_coverage_v1",
            "documents": [{"id": d.id, "sha256": hashlib.sha256(d.text.encode()).hexdigest()} for d in problem.documents.values()],
            "candidates": [asdict(c) for c in problem.candidates], "packs": [asdict(p) for p in ps]}


def verify_manifest(documents: Iterable[Document], manifest: dict) -> dict:
    if (manifest.get("schema_version") != 1 or manifest.get("budget_unit") != "source_words"
            or manifest.get("objective") != "weighted_source_coverage_v1"):
        raise ValueError("unsupported manifest schema, unit, or objective")
    docs = tuple(documents)
    hashes = [{"id": d.id, "sha256": hashlib.sha256(d.text.encode()).hexdigest()} for d in sorted(docs, key=lambda d: d.id)]
    if hashes != manifest["documents"]:
        raise ValueError("source hash mismatch")
    problem = EvidenceProblem(docs, [Candidate(**c) for c in manifest["candidates"]])
    packs = []
    from .model import Span
    for p in manifest["packs"]:
        packs.append(Pack(p["budget"], tuple(p["selected"]), p["cost"], p["utility"], tuple(Span(**s) for s in p["spans"])))
    return audit_ladder(problem, packs)
