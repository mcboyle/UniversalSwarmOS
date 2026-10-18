import time
from pathlib import Path

SEAT = "bd-ellm-test-scratch"
REVIEW_WT = Path("/home/mboyle/bd-review-wt")
VERDICTS_DIR = Path("/home/mboyle/bd-persist/verdicts")

with open("/home/mboyle/bd-persist/review-claims.tsv", "r") as f:
    lines = f.readlines()
last_line = next((l for l in reversed(lines) if SEAT in l), None)
print(f"last_line: {last_line}")
if last_line:
    parts = last_line.split("\t")
    is_released = last_line.startswith("RELEASED")
    cut_path = parts[1] if is_released else parts[0]
    print(f"is_released: {is_released}, cut_path: {cut_path}")

now = time.time()
candidates = []
if REVIEW_WT.exists(): candidates.extend(REVIEW_WT.rglob("VERDICT*.md"))
if VERDICTS_DIR.exists(): candidates.extend(VERDICTS_DIR.rglob("VERDICT*.md"))

v_path = None
for p in candidates:
    try:
        content = p.read_text()
        if SEAT in content:
            print(f"Found verdict: {p}")
            v_path = str(p)
            break
    except Exception:
        pass
        
if v_path:
    print(f"will kill because verdict found: {v_path}")
