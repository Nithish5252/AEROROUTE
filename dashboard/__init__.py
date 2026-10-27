# ============================================================
# AeroRoute -- Streamlit Dashboard Package
# File : dashboard/__init__.py
# ============================================================

import sys
from pathlib import Path

# Ensure project root is always in sys.path
_current = Path(__file__).resolve()
for _parent in [_current] + list(_current.parents):
    if (_parent / "dashboard").is_dir() and (_parent / "config").is_dir():
        if str(_parent) not in sys.path:
            sys.path.insert(0, str(_parent))
        break
