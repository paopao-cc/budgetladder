"""A small, deterministic BM25 retriever for offline demonstrations."""
from __future__ import annotations
from collections import Counter, defaultdict
from math import log
import re
from typing import Iterable
from .model import Candidate, Document

_STOP = frozenset("a an the of and or in on at to for is are was were be been being with by as it its this that which what who when where how why do does did from has have had not".split())


def terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[^\W_]+", text.casefold(), flags=re.UNICODE) if w not in _STOP]


def chunk_documents(documents: Iterable[Document], *, size: int = 80, overlap: int = 40) -> tuple[Candidate, ...]:
    """Sliding source-word windows, with no near-empty trailing duplicates."""
    if type(size) is not int or type(overlap) is not int or not 0 <= overlap < size:
        raise ValueError("require size > overlap >= 0")
    result = []
    for doc in sorted(documents, key=lambda d: d.id):
        length = len(re.findall(r"\S+", doc.text))
        for start in range(0, length, size - overlap):
            end = min(length, start + size)
            result.append(Candidate(f"{doc.id}:{start}-{end}", doc.id, start, end, 0.0))
            if end == length:
                break
    return tuple(result)


class BM25Index:
    def __init__(self, documents: Iterable[Document], chunks: Iterable[Candidate], *, k1: float = 1.5, b: float = 0.75):
        if k1 <= 0 or not 0 <= b <= 1:
            raise ValueError("invalid BM25 parameters")
        docs = {d.id: d.text for d in documents}
        self.chunks = tuple(sorted(chunks, key=lambda c: c.id))
        self.k1, self.b = k1, b
        words = {id_: re.findall(r"\S+", text) for id_, text in docs.items()}
        self.lengths = []
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, c in enumerate(self.chunks):
            if c.document_id not in words or not 0 <= c.start < c.end <= len(words[c.document_id]):
                raise ValueError("invalid chunk coordinates")
            counts = Counter(terms(" ".join(words[c.document_id][c.start:c.end])))
            self.lengths.append(sum(counts.values()))
            for term, count in counts.items():
                self.postings[term].append((i, count))
        self.average = sum(self.lengths) / max(1, len(self.lengths)) or 1.0

    def search(self, query: str, *, limit: int = 24) -> tuple[Candidate, ...]:
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be positive")
        scores: dict[int, float] = defaultdict(float)
        n = len(self.chunks)
        for term in sorted(set(terms(query))):
            posting = self.postings.get(term, ())
            idf = log(1 + (n - len(posting) + 0.5) / (len(posting) + 0.5))
            for i, tf in posting:
                norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.average)
                scores[i] += idf * tf * (self.k1 + 1) / (tf + norm)
        order = sorted(scores, key=lambda i: (-scores[i], self.chunks[i].id))[:limit]
        return tuple(Candidate(c.id, c.document_id, c.start, c.end, scores[i]) for i in order for c in [self.chunks[i]])
