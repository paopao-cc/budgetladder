"""Reproducible SQuAD source-span preservation, not generated-answer accuracy.

Input is an externally downloaded SQuAD 1.1 dev file, never shipped in this repo.
Output contains IDs and measurements, not Wikipedia passages or answer text.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import time
from budgetladder import (BM25Index, Candidate, Document, EvidenceProblem, audit_ladder,
                          chunk_documents, exact_ladder, independent_greedy,
                          nested_greedy, nested_rank_fill, plan_ladder, ranked_fill)


def retained(pack, doc_id, answers):
    return int(any(s.document_id == doc_id and s.char_start <= a['answer_start'] and
                   s.char_end >= a['answer_start'] + len(a['text']) for s in pack.spans for a in answers))


def removal(a, b):
    """Fraction of previously selected source words removed at the next rung."""
    old = {(s.document_id, i) for s in a.spans for i in range(s.start, s.end)}
    new = {(s.document_id, i) for s in b.spans for i in range(s.start, s.end)}
    return len(old - new) / max(1, len(old))


def bootstrap_difference(rows, left, right, seed=2026):
    """Paired bootstrap by article (not by correlated within-article questions)."""
    groups = {}
    by_q = {}
    for r in rows:
        by_q.setdefault(r['question_id'], {})[r['method']] = r
    for q in by_q.values():
        a, b = q[left], q[right]
        groups.setdefault(a['article'], []).append(sum(a['hits'])/len(a['hits']) - sum(b['hits'])/len(b['hits']))
    values = list(groups.values())
    rng = random.Random(seed)
    samples = []
    for _ in range(2000):
        draws = [rng.choice(values) for _ in values]
        samples.append(statistics.mean(x for group in draws for x in group))
    samples.sort()
    return {'difference': statistics.mean(x for group in values for x in group),
            'article_cluster_95_percentile_interval': [samples[49], samples[1949]],
            'clusters': len(values), 'replicates': 2000}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--config', type=Path, default=Path('configs/squad.json'))
    ap.add_argument('--output', type=Path, default=Path('experiments/results/squad'))
    args = ap.parse_args()
    cfg = json.loads(args.config.read_text())
    payload = args.data.read_bytes()
    raw = json.loads(payload)
    docs, questions = [], []
    invalid_answers = 0
    for article_idx, article in enumerate(raw['data']):
        for para_idx, para in enumerate(article['paragraphs']):
            doc_id = f'{article_idx:02d}:{para_idx:04d}'
            docs.append(Document(doc_id, para['context']))
            for q in para['qas']:
                # Validate gold offsets against the actual source, before using labels.
                answers = [a for a in q['answers'] if para['context'][a['answer_start']:a['answer_start']+len(a['text'])] == a['text']]
                invalid_answers += len(q['answers']) - len(answers)
                if answers:
                    questions.append((article_idx, doc_id, q, answers))
    random.Random(cfg['seed']).shuffle(questions)
    available_questions = len(questions)
    questions = questions[:cfg['questions']]
    if not questions:
        raise ValueError('benchmark requires at least one question')
    t0 = time.perf_counter()
    chunks = chunk_documents(docs, size=cfg['chunk_size'], overlap=cfg['overlap'])
    index = BM25Index(docs, chunks)
    index_seconds = time.perf_counter() - t0
    rows = []
    for num, (article, doc_id, q, answers) in enumerate(questions, 1):
        pool = index.search(q['question'], limit=cfg['candidates'])
        problem_docs = [d for d in docs if d.id in {c.document_id for c in pool}]
        pool_problem = EvidenceProblem(problem_docs, pool)
        pool_pack = pool_problem.pack((1 << len(pool)) - 1, 10**9)
        candidate_hit = retained(pool_pack, doc_id, answers)
        methods = {
            'rank_fill': lambda p: ranked_fill(p, cfg['budgets']),
            'independent_density': lambda p: independent_greedy(p, cfg['budgets']),
            'nested_rank': lambda p: nested_rank_fill(p, cfg['budgets']),
            'nested_greedy': lambda p: nested_greedy(p, cfg['budgets']),
            'ladder_beam_1': lambda p: plan_ladder(p, cfg['budgets'], beam_width=1),
            'ladder_beam': lambda p: plan_ladder(p, cfg['budgets'], beam_width=cfg['beam_width']),
        }
        for name, method in methods.items():
            # Fresh cache for fair measured planner latency; pool construction excluded.
            p = EvidenceProblem(problem_docs, pool)
            start = time.perf_counter()
            packs = method(p)
            seconds = time.perf_counter() - start
            audit_ladder(p, packs, require_nested=name not in ('rank_fill', 'independent_density'))
            hits = [retained(pack, doc_id, answers) for pack in packs]
            rows.append({'question_id': q['id'], 'article': article, 'method': name,
                         'pool_hit': candidate_hit, 'hits': hits,
                         'costs': [x.cost for x in packs], 'utility': [x.utility for x in packs],
                         'evicted_word_fraction': [removal(a,b) for a,b in zip(packs,packs[1:])],
                         'answer_losses': sum(a > b for a,b in zip(hits,hits[1:])),
                         'selected': [list(p.selected) for p in packs], 'seconds': seconds,
                         'evaluated_masks': len(p._cache)})
        if num % 25 == 0: print(f'{num}/{len(questions)} questions', flush=True)
    summary = {}
    for method in methods:
        rs = [r for r in rows if r['method'] == method]
        times = sorted(r['seconds'] * 1000 for r in rs)
        summary[method] = {'answer_span_recall': [statistics.mean(r['hits'][i] for r in rs) for i in range(len(cfg['budgets']))],
                           'mean_rung_recall': statistics.mean(x for r in rs for x in r['hits']),
                           'mean_utility': statistics.mean(x for r in rs for x in r['utility']),
                           'mean_cost': [statistics.mean(r['costs'][i] for r in rs) for i in range(len(cfg['budgets']))],
                           'mean_evicted_word_fraction': statistics.mean(x for r in rs for x in r['evicted_word_fraction']),
                           'answer_loss_transitions': sum(r['answer_losses'] for r in rs),
                           'p50_ms': statistics.median(times), 'p95_ms': times[int(.95*(len(times)-1))],
                           'mean_evaluated_masks': statistics.mean(r['evaluated_masks'] for r in rs)}
    report = {'dataset': 'SQuAD 1.1 development; retrieval over ALL paragraphs',
              'dataset_sha256': hashlib.sha256(payload).hexdigest(), 'config': cfg,
              'documents': len(docs), 'chunks': len(chunks), 'questions': len(questions),
              'available_questions': available_questions, 'invalid_gold_annotations_filtered': invalid_answers,
              'candidate_pool_recall': statistics.mean(r['pool_hit'] for r in rows if r['method']=='ladder_beam'),
              'python': platform.python_version(), 'platform': platform.system()+' '+platform.machine(),
              'index_build_seconds': index_seconds, 'summary': summary,
              'paired_recall_difference': {name: bootstrap_difference(rows, 'ladder_beam', name, cfg['seed']) for name in ['independent_density','nested_greedy','rank_fill','nested_rank']},
              'notes': ['No answer labels used for retrieval, scoring, or planning.', 'Rungs within a question are correlated; clustered intervals are exploratory.', 'Latency is local CPU planner-only, single pass, without index or audit.']}
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'records.jsonl').write_text(''.join(json.dumps(r,sort_keys=True)+'\n' for r in rows))
    (args.output/'summary.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,indent=2,sort_keys=True))


if __name__ == '__main__': main()
