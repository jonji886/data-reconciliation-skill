"""Excel / CSV reconciliation MVP."""

# Some macOS environments expose a very large CPU count to OpenBLAS. Limiting
# the default worker count avoids an import-time deadlock for pandas/numpy while
# still allowing callers to override it explicitly before importing the package.
import os

for _variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")

__version__ = "0.1.0"
