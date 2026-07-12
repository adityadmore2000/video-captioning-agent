"""Make both the production ``src/`` package and the ``experiments/`` package importable.

Experiments tests reuse the production frame sampler / VLM client / style generator from
``src/`` (per EXPERIMENT_TRACKING.md: "reuse the existing production components rather than
reimplementing them"), so ``src/`` must be on ``sys.path`` here just as it is for the
production test suite under ``tests/``.
"""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
EXPERIMENTS_DIR = ROOT / "experiments"

for path in (SRC_DIR, EXPERIMENTS_DIR):
    resolved = str(path)
    if resolved not in sys.path:
        sys.path.insert(0, resolved)