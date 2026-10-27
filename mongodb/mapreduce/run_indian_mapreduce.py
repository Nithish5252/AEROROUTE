# ============================================================
# AeroRoute -- Phase 3: Indian MapReduce Pipeline Runner
# File : mongodb/mapreduce/run_indian_mapreduce.py
# Usage: python mongodb/mapreduce/run_indian_mapreduce.py [--job A|B|C|D|E|ALL] [--limit N]
# ============================================================

import sys
from pathlib import Path

# Forward to the canonical scripts runner
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_indian_mapreduce import main

if __name__ == "__main__":
    main()
