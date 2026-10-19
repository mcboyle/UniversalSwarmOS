#!/usr/bin/env python3
"""
bd-oracle-seat-daemon.py — Active Dual-Node Browser Oracle Seat Daemon (Rule 79).

Drives `/home/mboyle/bin/bd-oracle` across BattleStation (`10.0.10.137:9222`) and
Bittorrent (`10.0.70.181:9222`) at $0 marginal cost to:
1. Drain any explicit oracle request in `/home/mboyle/bd-persist/inbox/bd-oracle-swarm-1/*.md`
2. Autonomously adjudicate open architectural questions (`Q-*.md`, `ESCALATE-*.md`) and
   contested `REFUTE` lens verdicts under `/home/mboyle/bd-persist/harness-work/O1789/`,
   writing structured multi-oracle consensus receipts to
   `/home/mboyle/bd-persist/harness-work/O1789/oracle-seats/bd-oracle-swarm-1/`.
"""

import glob
import json
import subprocess
import time
from pathlib import Path


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def run_bd_oracle(prompt: str) -> tuple[str, float]:
    t0 = time.monotonic()
    r = subprocess.run(
        [
            "/home/mboyle/bin/bd-oracle",
            "--oracle",
            "all",
            "--node",
            "auto",
            "--timeout",
            "45",
            "--json",
            "--consensus",
            prompt,
        ],
        capture_output=True,
        text=True,
        timeout=110,
        check=False,
    )
    elapsed = round(time.monotonic() - t0, 2)
    out = r.stdout.strip() or r.stderr.strip() or "{}"
    return out, elapsed


def discover_question_or_refute(done_set: set[str]) -> tuple[str, Path, str] | None:
    try:
        raw = subprocess.check_output(["find", "/home/mboyle/bd-persist/harness-work/O1789", "-maxdepth", "4", "-type", "f", "(", "-name", "Q-*.md", "-o", "-name", "ESCALATE-*.md", "-o", "-name", "VERDICT-*.md", "-o", "-name", "REFUTE-*.md", ")"], text=True, timeout=5, stderr=subprocess.DEVNULL)
        paths = [Path(p) for p in raw.splitlines() if p.strip()]
    except Exception:
        paths = []
    cands = sorted(paths, key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for cp in cands[:80]:
        key = str(cp.relative_to("/home/mboyle/bd-persist"))
        if key in done_set:
            continue
        try:
            txt = cp.read_text(encoding="utf-8", errors="replace")
            if cp.name.startswith("VERDICT-") and "REFUTE" not in txt:
                continue
            return (key, cp, txt[:3500])
        except Exception:
            continue
    return None


def main() -> None:
    import os
    seat = "bd-oracle-swarm-1"
    if os.environ.get("BD_FORCE_ORACLE_SEAT") != "1" and Path("/home/mboyle/bd-persist/state/GOD-ORACLE-SWARM-1-STOPPED.md").exists():
        print(f"[{now_iso()}] [{seat}] Retired per O3387 (GOD-ORACLE-SWARM-1-STOPPED.md); exiting.")
        return
    inbox_dir = Path(f"/home/mboyle/bd-persist/inbox/{seat}")
    done_dir = inbox_dir / "processed"
    out_dir = Path(f"/home/mboyle/bd-persist/harness-work/O1789/oracle-seats/{seat}")
    inbox_dir.mkdir(parents=True, exist_ok=True)
    done_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "LEDGER.jsonl"

    done_items: set[str] = set()
    if ledger_path.exists():
        for line in ledger_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines():
            try:
                done_items.add(json.loads(line).get("item", ""))
            except Exception:
                pass

    print(
        f"[{now_iso()}] [{seat}] Dual Browser Oracle Seat online (.137:9222 BattleStation + .181:9222 Bittorrent)",
        flush=True,
    )

    # Initial status check
    st = subprocess.run(
        ["/home/mboyle/bin/bd-oracle", "--status"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    for l in (st.stdout or "").splitlines()[:8]:
        print(f"  {l}", flush=True)

    while True:
        try:
            # 1. Drain explicit inbox requests
            for mpath in sorted(glob.glob(str(inbox_dir / "*.md"))):
                mp = Path(mpath)
                txt = mp.read_text(encoding="utf-8", errors="replace")
                print(
                    f"[{now_iso()}] [{seat}] ORACLE INBOX query: {mp.name}...",
                    flush=True,
                )
                out, elapsed = run_bd_oracle(
                    f"Boylenet Rule 79 Oracle Consensus Query ({mp.name}):\n{txt[:3500]}\nRespond with BOARD or REFUTE and concise rationale."
                )
                res_path = out_dir / f"ORACLE-INBOX-{mp.stem}.md"
                res_path.write_text(
                    f"# Oracle Consensus Result (`{mp.name}`)\n- **Elapsed**: `{elapsed}s`\n\n```json\n{out}\n```\n",
                    encoding="utf-8",
                )
                mp.rename(done_dir / mp.name)
                print(
                    f"[{now_iso()}] [{seat}] DONE ORACLE INBOX {mp.name} in {elapsed}s -> {res_path.name}",
                    flush=True,
                )

            # 2. Autonomous adjudication of Q-*.md / ESCALATE-*.md / REFUTE verdicts
            found = discover_question_or_refute(done_items)
            if found:
                key, cp, txt = found
                print(
                    f"[{now_iso()}] [{seat}] ORACLE adjudicating `{key}` via .137:9222 & .181:9222...",
                    flush=True,
                )
                prompt = (
                    f"Evaluate Boylenet artifact `{key}` under Fleet Rule 86 (Behavioral Defect vs Mutation Coverage Severance):\n\n"
                    f"{txt}\n\n"
                    "Provide a concise adjudication: BOARD, BOARD-WITH-ADVISORY, or REFUTE with 1-sentence reason."
                )
                out, elapsed = run_bd_oracle(prompt)
                safe_name = key.replace("/", "__").replace(".md", "")
                res_path = out_dir / f"ORACLE-{safe_name}.md"
                res_path.write_text(
                    f"# Dual Browser Oracle Adjudication: `{key}`\n- **Timestamp**: `{now_iso()}`\n- **Elapsed**: `{elapsed}s`\n\n```json\n{out}\n```\n",
                    encoding="utf-8",
                )
                done_items.add(key)
                with ledger_path.open("a", encoding="utf-8") as lf:
                    lf.write(
                        json.dumps(
                            {
                                "ts": now_iso(),
                                "seat": seat,
                                "item": key,
                                "elapsed_s": elapsed,
                                "out": str(res_path),
                            }
                        )
                        + "\n"
                    )
                print(
                    f"[{now_iso()}] [{seat}] DONE ORACLE `{key}` in {elapsed}s -> {res_path.name}",
                    flush=True,
                )
                time.sleep(5)
                continue
        except Exception as e:
            print(f"[{now_iso()}] [{seat}] Oracle cycle error: {e}", flush=True)
        time.sleep(15)


if __name__ == "__main__":
    main()
