"""Share of 3D pixels that changed between <name>-a.png and <name>-b.png (per-channel delta > 12)."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

d = Path(sys.argv[1])
for a in sorted(d.glob("*-a.png")):
    b = a.with_name(a.name.replace("-a.png", "-b.png"))
    x = np.asarray(Image.open(a).convert("RGB"), dtype=int)
    y = np.asarray(Image.open(b).convert("RGB"), dtype=int)
    changed = (np.abs(x - y).max(axis=2) > 12).mean()
    print(f"{a.name[:-6]:10s} {changed * 100:5.1f}% of the 3D view changed")
