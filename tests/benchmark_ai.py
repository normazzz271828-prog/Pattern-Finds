"""Run on ECS under a bounded systemd scope, using non-user test fixtures."""
from pathlib import Path
from io import BytesIO
import json
import resource
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, "/opt/wenshi/app")
from backend.segmentation import foreground_mask, warmup, MODEL_PATH

folder = Path(sys.argv[1])
start = time.monotonic()
warmup()
results = {"model": MODEL_PATH.name, "warmup_seconds": round(time.monotonic()-start, 3)}
for name in ["textured-motif.png", "official-sample.jpg"]:
    image = Image.open(folder/name).convert("RGB")
    image.thumbnail((1600, 1600))
    start = time.monotonic()
    mask = foreground_mask(image)
    duration = time.monotonic()-start
    result = image.convert("RGBA")
    result.putalpha(mask)
    result.save(folder/(MODEL_PATH.stem+"-"+name+".png"))
    alpha = np.asarray(mask) > 128
    entry = {"seconds": round(duration, 3), "foreground_fraction": float(alpha.mean())}
    if name == "textured-motif.png":
        truth = np.asarray(Image.open(folder/"textured-groundtruth.png")) > 128
        entry["iou"] = float(np.sum(truth & alpha)/np.sum(truth | alpha))
        entry["foreground_retention"] = float(alpha[truth].mean())
        entry["background_retention"] = float(alpha[~truth].mean())
        assert entry["iou"] > .5, entry
    results[name] = entry
try:
    foreground_mask(Image.open(folder/"blank.png"))
    raise AssertionError("Uniform image should be rejected")
except ValueError:
    results["blank_rejected"] = True
results["peak_rss_mb"] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024, 1)
print(json.dumps(results, indent=2))
