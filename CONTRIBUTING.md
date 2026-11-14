# Contributing

Use Python 3.10+; runtime changes should retain a CPU-only path. Install with `python -m pip install -e .`, then run `python -m unittest discover -s tests -v`. New planner behavior needs invariant tests and, when relevant, a small exact-reference comparison. Keep whitespace-word budgets distinct from model tokens. Do not commit datasets, secrets or personal source documents.

For benchmark changes, preserve original configurations and raw records, state new sampling choices, and compare methods on identical pools and cost accounting. A favorable source-retention metric is not proof of better generated answers. Open an issue describing a reproducible counterexample or a concrete proposed improvement before large API changes.
