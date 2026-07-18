import os
import sys

# Ensure the repository root is importable so `import src...` works no matter
# how the tests are launched (unittest discovery, pytest, or a single file).
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
