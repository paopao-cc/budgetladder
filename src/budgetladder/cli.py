"""JSON input, portable text output, and independently verifiable manifests."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from . import (BM25Index, Document, EvidenceProblem, audit_ladder, chunk_documents,
               exact_ladder, export_ladder, plan_ladder, nested_rank_fill, verify_manifest)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nested RAG evidence plans; budgets count source words, not model tokens.")
    parser.add_argument("input", type=Path, help="JSON: documents [{id,text}], query")
    parser.add_argument("--budgets", default="80,160,240")
    parser.add_argument("--size", type=int, default=80)
    parser.add_argument("--overlap", type=int, default=40)
    parser.add_argument("--candidates", type=int, default=24)
    parser.add_argument("--beam-width", type=int, default=24)
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--strategy", choices=["beam", "nested-rank"], default="beam")
    parser.add_argument("--output", type=Path, help="write manifest JSON")
    parser.add_argument("--verify", type=Path, help="verify a manifest against input source documents")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.input.read_text(encoding="utf-8"))
        docs = tuple(Document(**d) for d in data["documents"])
        if args.verify:
            print(json.dumps(verify_manifest(docs, json.loads(args.verify.read_text(encoding="utf-8"))), indent=2))
            return 0
        budgets = tuple(int(b.strip()) for b in args.budgets.split(","))
        chunks = chunk_documents(docs, size=args.size, overlap=args.overlap)
        pool = BM25Index(docs, chunks).search(data["query"], limit=args.candidates)
        problem = EvidenceProblem(docs, pool)
        if args.exact and args.strategy != "beam":
            raise ValueError("--exact cannot be combined with --strategy nested-rank")
        packs = (exact_ladder(problem, budgets) if args.exact else
                 nested_rank_fill(problem, budgets) if args.strategy == "nested-rank" else
                 plan_ladder(problem, budgets, beam_width=args.beam_width))
        print("BudgetLadder | source-word budgets | " + data["query"])
        for p in packs:
            print(f"\nBudget {p.budget:>4}  used {p.cost:>4}  coverage {p.utility:.4f}  chunks {len(p.selected)}")
            for s in p.spans:
                print(f"  [{s.document_id} words {s.start}:{s.end}, chars {s.char_start}:{s.char_end}]")
                print("  " + s.text)
        print("\nAudit: " + json.dumps(audit_ladder(problem, packs), sort_keys=True))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(export_ladder(problem, packs), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, f"budgetladder: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
