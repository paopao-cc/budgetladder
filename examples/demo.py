"""Run from the checkout after installing: python examples/demo.py."""
from pathlib import Path
from budgetladder.cli import main
raise SystemExit(main([str(Path(__file__).with_name("field-notes.json")), "--budgets", "32,64,96", "--size", "32", "--overlap", "16", "--output", "output/demo-manifest.json"]))
