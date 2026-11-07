import os

# OpenBLAS per-thread buffers exhausted memory on an 8 GB laptop at first forecast load; must be set before numpy loads.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
