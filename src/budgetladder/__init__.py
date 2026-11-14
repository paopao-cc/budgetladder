"""Auditable nested evidence plans, without models or network calls."""
from .model import Candidate, Document, EvidenceProblem, Pack, Span
from .planner import exact_ladder, independent_greedy, nested_greedy, nested_rank_fill, plan_ladder, ranked_fill
from .retrieval import BM25Index, chunk_documents
from .audit import audit_ladder, export_ladder, verify_manifest

__version__ = "1.0.0"
__all__ = ["Candidate", "Document", "EvidenceProblem", "Pack", "Span", "BM25Index",
           "chunk_documents", "plan_ladder", "exact_ladder", "independent_greedy",
           "nested_greedy", "nested_rank_fill", "ranked_fill", "audit_ladder", "export_ladder", "verify_manifest"]
