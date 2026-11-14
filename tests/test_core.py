from dataclasses import replace
import copy
import itertools
import json
import random
import unittest
from budgetladder import *


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.doc = Document('d', '  α\tβ  γ\nδ\u2003ε  ζ ')
        self.cs = (Candidate('a', 'd', 0, 3, 2), Candidate('b', 'd', 2, 5, 1))
        self.p = EvidenceProblem([self.doc], self.cs)

    def test_union_and_exact_unicode_slice(self):
        pack = self.p.pack(3, 5)
        self.assertEqual(pack.cost, 5)
        self.assertEqual(len(pack.spans), 1)
        self.assertEqual(pack.spans[0].text, 'α\tβ  γ\nδ\u2003ε')
        self.assertAlmostEqual(pack.utility, 1)

    def test_disjoint_spans_not_fabricated(self):
        p = EvidenceProblem([self.doc], [Candidate('a', 'd', 0, 1, 1), Candidate('b', 'd', 4, 6, 1)])
        self.assertEqual([s.text for s in p.pack(3, 3).spans], ['α', 'ε  ζ'])

    def test_duplicate_text_in_distinct_sources_is_not_deduplicated(self):
        p = EvidenceProblem([Document('a', 'same words'), Document('b', 'same words')],
                            [Candidate('a', 'a', 0, 2, 1), Candidate('b', 'b', 0, 2, 1)])
        self.assertEqual(p.pack(3, 4).cost, 4)

    def test_invalid_inputs(self):
        for c in [replace(self.cs[0], start=-1), replace(self.cs[0], end=90), replace(self.cs[0], score=float('nan')), replace(self.cs[0], score=-1), replace(self.cs[0], end=2.5)]:
            with self.assertRaises(ValueError): EvidenceProblem([self.doc], [c])
        with self.assertRaises(ValueError): EvidenceProblem([self.doc, self.doc], [])
        with self.assertRaises(ValueError): EvidenceProblem([self.doc], [self.cs[0]] * 2)
        for mask in [-1, 4, True]:
            with self.assertRaises(ValueError): self.p.metrics(mask)

    def test_large_finite_scores_normalize_without_overflow(self):
        p = EvidenceProblem([self.doc], [replace(c, score=1e308) for c in self.cs])
        self.assertAlmostEqual(p.metrics(3)[1], 1)

    def test_zero_scores(self):
        p = EvidenceProblem([self.doc], [replace(c, score=0) for c in self.cs])
        self.assertEqual(p.metrics(3)[1], 0)
        self.assertEqual(plan_ladder(p, [0, 2, 5])[-1].cost, 0)

    def test_monotone_objective_and_submodularity(self):
        for a in range(4):
            for b in range(4):
                f = lambda m: self.p.metrics(m)[1]
                self.assertGreaterEqual(f(a) + f(b) + 1e-12, f(a | b) + f(a & b))
                self.assertLessEqual(f(a), f(a | b) + 1e-12)


class PlannerTests(unittest.TestCase):
    def problem(self, seed=7, n=7):
        rng = random.Random(seed)
        docs = [Document('a', ' '.join('w'+str(i) for i in range(25))), Document('b', ' '.join('v'+str(i) for i in range(25)))]
        cs = []
        for i in range(n):
            start = rng.randrange(20)
            cs.append(Candidate(str(i), rng.choice(['a', 'b']), start, start + rng.randrange(1, 6), rng.random()))
        return EvidenceProblem(docs, cs)

    def test_exact_matches_exhaustive_nested_chains(self):
        for seed in range(8):
            p = self.problem(seed, n=5)
            bs = [3, 7, 11]
            feasible = [[m for m in range(32) if p.metrics(m)[0] <= b] for b in bs]
            brute = max(sum(p.metrics(m)[1] for m in ms) for ms in itertools.product(*feasible) if all(a & b == a for a, b in zip(ms, ms[1:])))
            self.assertAlmostEqual(sum(x.utility for x in exact_ladder(p, bs)), brute)

    def test_wide_beam_matches_exact(self):
        for seed in range(20):
            p = self.problem(seed)
            beam = plan_ladder(p, [3, 7, 12], beam_width=128)
            exact = exact_ladder(p, [3, 7, 12])
            self.assertAlmostEqual(sum(x.utility for x in beam), sum(x.utility for x in exact))

    def test_randomized_nested_and_budget_invariants(self):
        for seed in range(100):
            p = self.problem(seed, n=12)
            packs = plan_ladder(p, [0, 3, 9, 20], beam_width=6)
            self.assertTrue(audit_ladder(p, packs)['verified'])
            for a, b in zip(packs, packs[1:]):
                self.assertLessEqual(a.utility, b.utility + 1e-12)
                self.assertTrue(set(a.selected) <= set(b.selected))

    def test_input_order_invariance(self):
        p = self.problem()
        reverse = EvidenceProblem(reversed(tuple(p.documents.values())), reversed(p.candidates))
        self.assertEqual(plan_ladder(p, [3, 7, 12]), plan_ladder(reverse, [3, 7, 12]))

    def test_invalid_options_and_empty_pool(self):
        p = self.problem()
        for bs in [[], [2, 2], [3, 1], [-1], [True]]:
            with self.assertRaises(ValueError): plan_ladder(p, bs)
        with self.assertRaises(ValueError): plan_ladder(p, [3], beam_width=0)
        self.assertEqual(plan_ladder(EvidenceProblem([], []), [0, 1])[-1].cost, 0)
        with self.assertRaises(ValueError): exact_ladder(self.problem(n=17), [2])

    def test_baselines_share_cost_and_keep_valid_sources(self):
        p = self.problem()
        for method in [independent_greedy, ranked_fill, nested_greedy, nested_rank_fill]:
            packs = method(p, [3, 7, 12])
            self.assertTrue(audit_ladder(p, packs, require_nested=False)['verified'])


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.docs = [Document('a', 'one two three four five')]
        self.p = EvidenceProblem(self.docs, [Candidate('a', 'a', 0, 3, 1), Candidate('b', 'a', 2, 5, 1)])
        self.packs = plan_ladder(self.p, [3, 5])
        self.manifest = export_ladder(self.p, self.packs)

    def test_round_trip(self):
        manifest = json.loads(json.dumps(self.manifest))
        self.assertTrue(verify_manifest(self.docs, manifest)['verified'])

    def test_tampering_rejected(self):
        for field, value in [('cost', 0), ('utility', 999), ('utility', float('nan'))]:
            m = copy.deepcopy(self.manifest)
            m['packs'][0][field] = value
            with self.assertRaises(ValueError): verify_manifest(self.docs, m)
        m = copy.deepcopy(self.manifest)
        m['packs'][0]['spans'][0]['text'] = 'invented'
        with self.assertRaises(ValueError): verify_manifest(self.docs, m)
        with self.assertRaises(ValueError): verify_manifest([Document('a', 'modified')], self.manifest)

    def test_eviction_rejected(self):
        packs = [self.p.pack(1, 3), self.p.pack(2, 5)]
        with self.assertRaises(ValueError): audit_ladder(self.p, packs)


class RetrievalTests(unittest.TestCase):
    def test_search_and_empty_query(self):
        ds = [Document('a', 'Mars rover solar energy power'), Document('b', 'ocean whales marine biology')]
        chunks = chunk_documents(ds, size=3, overlap=1)
        index = BM25Index(ds, chunks)
        self.assertEqual(index.search('solar energy')[0].document_id, 'a')
        self.assertEqual(index.search('the and of'), ())
        with self.assertRaises(ValueError): chunk_documents(ds, size=3, overlap=3)
        with self.assertRaises(ValueError): index.search('rover', limit=0)

    def test_no_short_tail_duplicate(self):
        cs = chunk_documents([Document('d', 'a b c d e')], size=4, overlap=2)
        self.assertEqual([(c.start, c.end) for c in cs], [(0, 4), (2, 5)])


if __name__ == '__main__': unittest.main()
