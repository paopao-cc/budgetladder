"""Immutable source coordinates and a common objective/cost model.

Budget units are Unicode whitespace-delimited source words, NOT model tokens.
All intervals are half-open. Source documents must remain unchanged within a plan.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isfinite
import re
from typing import Iterable


@dataclass(frozen=True)
class Document:
    id: str
    text: str


@dataclass(frozen=True)
class Candidate:
    id: str
    document_id: str
    start: int  # source word index, inclusive
    end: int    # source word index, exclusive
    score: float


@dataclass(frozen=True)
class Span:
    document_id: str
    start: int
    end: int
    char_start: int
    char_end: int
    text: str


@dataclass(frozen=True)
class Pack:
    budget: int
    selected: tuple[str, ...]
    cost: int
    utility: float
    spans: tuple[Span, ...]

    @property
    def text(self) -> str:
        """Exact source slices joined by two newlines; no citation headers."""
        return "\n\n".join(s.text for s in self.spans)


class EvidenceProblem:
    """Canonical candidate pool shared by every rung and baseline.

    F(S) = sum_i normalized_score_i * |U(S) intersect span_i| / |span_i|.
    Cost is |U(S)|. F is weighted source coverage, not answer probability.
    Integer bitsets make union costs exact for the declared word unit.
    """

    def __init__(self, documents: Iterable[Document], candidates: Iterable[Candidate]):
        docs = tuple(documents)
        if any(not isinstance(d.id, str) or not d.id for d in docs):
            raise ValueError("document ids must be nonempty strings")
        if len({d.id for d in docs}) != len(docs):
            raise ValueError("duplicate document id")
        self.documents = {d.id: d for d in sorted(docs, key=lambda d: d.id)}
        self.words = {d.id: tuple(re.finditer(r"\S+", d.text)) for d in docs}
        self.candidates = tuple(sorted(candidates, key=lambda c: c.id))
        if len(self.candidates) > 64:
            raise ValueError("at most 64 candidates; retrieve a smaller pool first")
        if any(not isinstance(c.id, str) or not c.id for c in self.candidates):
            raise ValueError("candidate ids must be nonempty strings")
        if len({c.id for c in self.candidates}) != len(self.candidates):
            raise ValueError("duplicate candidate id")
        offsets = {}
        pos = 0
        # Allocate only source positions inside the pool, avoiding huge sparse bitsets.
        positions = {}
        for c in self.candidates:
            if c.document_id not in self.documents:
                raise ValueError("unknown candidate document")
            if type(c.start) is not int or type(c.end) is not int:
                raise ValueError("source word offsets must be integers")
            if not 0 <= c.start < c.end <= len(self.words[c.document_id]):
                raise ValueError("candidate interval outside source")
            if not isfinite(c.score) or c.score < 0:
                raise ValueError("scores must be finite and nonnegative")
            positions.setdefault(c.document_id, set()).update(range(c.start, c.end))
        for doc_id in sorted(positions):
            for word in sorted(positions[doc_id]):
                offsets[(doc_id, word)] = pos
                pos += 1
        self.coverage = tuple(sum(1 << offsets[(c.document_id, w)]
                                  for w in range(c.start, c.end)) for c in self.candidates)
        scale = max((c.score for c in self.candidates), default=0.0)
        scaled = tuple(c.score / scale if scale else 0.0 for c in self.candidates)
        total = sum(scaled)
        self.weights = tuple(w / total if total else 0.0 for w in scaled)
        self._cache: dict[int, tuple[int, float, int]] = {0: (0, 0.0, 0)}
        self._limit = 1 << len(self.candidates)

    def metrics(self, mask: int) -> tuple[int, float, int]:
        """Return union cost, weighted coverage, and source-position bitset."""
        if type(mask) is not int or not 0 <= mask < self._limit:
            raise ValueError("invalid candidate mask")
        if mask not in self._cache:
            bit = mask & -mask
            union = self.metrics(mask ^ bit)[2] | self.coverage[bit.bit_length() - 1]
            utility = sum(w * (union & cov).bit_count() / cov.bit_count()
                          for w, cov in zip(self.weights, self.coverage))
            self._cache[mask] = (union.bit_count(), utility, union)
        return self._cache[mask]

    def mask(self, ids: Iterable[str]) -> int:
        lookup = {c.id: i for i, c in enumerate(self.candidates)}
        result = 0
        for id_ in ids:
            if id_ not in lookup:
                raise ValueError("unknown candidate id: " + str(id_))
            result |= 1 << lookup[id_]
        return result

    def pack(self, mask: int, budget: int) -> Pack:
        cost, utility, _ = self.metrics(mask)
        if type(budget) is not int or budget < 0 or cost > budget:
            raise ValueError("invalid or exceeded budget")
        selected = [c for i, c in enumerate(self.candidates) if mask & (1 << i)]
        spans = []
        for doc_id in self.documents:
            intervals = sorted((c.start, c.end) for c in selected if c.document_id == doc_id)
            merged: list[tuple[int, int]] = []
            for start, end in intervals:
                if merged and start <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
                else:
                    merged.append((start, end))
            for start, end in merged:
                chars = self.words[doc_id]
                a, b = chars[start].start(), chars[end - 1].end()
                spans.append(Span(doc_id, start, end, a, b, self.documents[doc_id].text[a:b]))
        return Pack(budget, tuple(c.id for c in selected), cost, utility, tuple(spans))
