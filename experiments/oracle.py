"""Exact-objective gaps on generated interval pools; NOT empirical QA evidence."""
import argparse
import json
from pathlib import Path
import random
import statistics
import time
from budgetladder import Candidate, Document, EvidenceProblem, exact_ladder, plan_ladder, nested_greedy

ap=argparse.ArgumentParser()
ap.add_argument('--cases',type=int,default=100)
ap.add_argument('--output',type=Path,default=Path('experiments/results/oracle.json'))
a=ap.parse_args()
rows=[]
for seed in range(a.cases):
    rng=random.Random(seed)
    ds=[Document(str(i),' '.join('w'+str(j) for j in range(60))) for i in range(3)]
    cs=[]
    for i in range(10):
        start=rng.randrange(45)
        cs.append(Candidate(str(i),str(rng.randrange(3)),start,start+rng.randrange(3,16),rng.uniform(.1,1)))
    bs=[12,24,40]
    row={'seed':seed,'budgets':bs}
    for name, method in [('exact',exact_ladder),('beam1',lambda p,b:plan_ladder(p,b,beam_width=1)),('beam16',lambda p,b:plan_ladder(p,b,beam_width=16)),('nested_greedy',nested_greedy)]:
        p=EvidenceProblem(ds,cs);t=time.perf_counter();packs=method(p,bs)
        row[name]={'sum_utility':sum(x.utility for x in packs),'seconds':time.perf_counter()-t}
    rows.append(row)
summary={name:{'mean_relative_objective_gap':statistics.mean(1-r[name]['sum_utility']/r['exact']['sum_utility'] for r in rows),'max_relative_objective_gap':max(1-r[name]['sum_utility']/r['exact']['sum_utility'] for r in rows),'mean_ms':1000*statistics.mean(r[name]['seconds'] for r in rows)} for name in ['beam1','beam16','nested_greedy']}
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps({'seed_range':[0,a.cases-1],'cases':rows,'summary':summary},indent=2)+'\n')
print(json.dumps(summary,indent=2))
