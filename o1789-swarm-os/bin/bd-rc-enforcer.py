import concurrent.futures
import datetime
import subprocess

HOSTS = [
    "127.0.0.1",
    "10.0.70.51",
    "10.0.70.52",
    "10.0.70.80",
    "10.0.70.81",
    "10.0.70.82",
    "10.0.70.84",
    "10.0.70.85",
    "10.0.70.184",
    "10.0.70.193",
    "10.0.70.194",
    "10.0.70.196",
    "10.0.70.249",
]
LOG_PATH = "/var/tmp/bd-rc-enforcer.log"
REMOTE_SCRIPT = r"""
import glob, os, re, subprocess, time

now_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def log_event(seat, case_id, result):
    line = f"{now_ts}\t{seat}\t{case_id}\t{result}\n"
    try:
        with open("/var/tmp/bd-rc-enforcer.log", "a") as lf:
            lf.write(line)
    except Exception:
        pass
    print(line.strip())

def get_live_resumed_uuids():
    held = {}
    for cmd_path in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            pid = int(cmd_path.split("/")[2])
            raw = open(cmd_path, "rb").read().decode("utf-8", errors="ignore")
            parts = [p for p in raw.split("\x00") if p]
            if not parts:
                continue
            joined = " ".join(parts)
            if "claude" not in joined:
                continue
            for m in re.finditer(r"--resume\s+([0-9a-fA-F-]{36})", joined):
                u = m.group(1)
                held.setdefault(u, []).append(pid)
        except Exception:
            pass
    return held

def get_pane_tree_pids(pane_pid):
    pids = {pane_pid}
    changed = True
    while changed:
        changed = False
        for stat_path in glob.glob("/proc/[0-9]*/stat"):
            try:
                content = open(stat_path, "r").read()
                rparen = content.rfind(")")
                pid = int(content[:content.find("(")].strip())
                rest = content[rparen+2:].split()
                ppid = int(rest[1])
                if ppid in pids and pid not in pids:
                    pids.add(pid)
                    changed = True
            except Exception:
                pass
    return pids

def has_oauth_token_env(tree_pids):
    for pid in tree_pids:
        try:
            raw = open(f"/proc/{pid}/environ", "rb").read().decode("utf-8", errors="ignore")
            for entry in raw.split("\x00"):
                if entry.startswith("CLAUDE_CODE_OAUTH_TOKEN=") and len(entry) > len("CLAUDE_CODE_OAUTH_TOKEN="):
                    return True
        except Exception:
            pass
    return False

def find_own_uuid(sess, pool, tree_pids):
    for pid in tree_pids:
        try:
            raw = open(f"/proc/{pid}/cmdline", "rb").read().decode("utf-8", errors="ignore")
            joined = " ".join(p for p in raw.split("\x00") if p)
            m = re.search(r"--resume\s+([0-9a-fA-F-]{36})", joined)
            if m:
                return m.group(1)
        except Exception:
            pass

    uuid_file = f"/var/tmp/bd-seat-uuid-{sess}.txt"
    if os.path.exists(uuid_file):
        try:
            u = open(uuid_file).read().strip()
            if re.match(r"^[0-9a-fA-F-]{36}$", u):
                return u
        except Exception:
            pass

    SINGLETON_DIRS = {
        "bd-usage-a-A": "-var-tmp-bd-seats-usage-a",
        "bd-usage-b-B": "-var-tmp-bd-seats-usage-b",
        "bd-usage-c-C": "-var-tmp-bd-seats-usage-c",
        "bd-usage-d-D": "-var-tmp-bd-seats-usage-d",
    }
    proj_sub = SINGLETON_DIRS.get(sess)
    if proj_sub:
        cands = glob.glob(f"/home/mboyle/.claude-{pool}/projects/{proj_sub}/*.jsonl")
        if cands:
            newest = max(cands, key=os.path.getmtime)
            return os.path.basename(newest).replace(".jsonl", "")

    return None

def is_idle_strict(tail):
    busy_markers = (
        "esc to interrupt",
        "Thinking",
        "Gesticulating",
        "Sautéed",
        "Crunched",
        "Cooked",
        "Running",
        "Waiting for",
        "Enter to select",
        "Press up to edit queued messages",
    )
    if any(b in tail for b in busy_markers):
        return False
    # Check that there is an empty `❯` prompt line near the bottom
    lines = [l.strip() for l in tail.splitlines() if l.strip()]
    has_empty_prompt = any(l in ("❯", "❯\xa0") for l in lines[-6:])
    return has_empty_prompt

try:
    out = subprocess.check_output(
        ["tmux", "list-panes", "-a", "-F", "#{session_name}\t#{pane_pid}\t#{pane_current_path}"],
        stderr=subprocess.DEVNULL, text=True
    )
except Exception:
    raise SystemExit(0)

held_uuids = get_live_resumed_uuids()
attempted_rc_path = "/var/tmp/bd-rc-b-attempted.txt"
try:
    attempted_rc = set(open(attempted_rc_path).read().splitlines()) if os.path.exists(attempted_rc_path) else set()
except Exception:
    attempted_rc = set()

for line in out.splitlines():
    parts = line.strip().split("\t")
    if len(parts) < 3:
        continue
    sess, pane_pid_s, cwd = parts[0], parts[1], parts[2]
    # Rule D: Never type into bd-pm-B
    if sess == "bd-pm-B":
        continue
    if not (sess.startswith("bd-") or sess.startswith("usage-")):
        continue
    if any(sess.startswith(p) for p in ("bd-kimi-", "bd-local-", "cx-")):
        continue
    m = re.search(r"-([ABCD])$", sess)
    if not m:
        continue
    pool = m.group(1).lower()
    pane_pid = int(pane_pid_s)
    tree_pids = get_pane_tree_pids(pane_pid)

    try:
        pane = subprocess.check_output(["tmux", "capture-pane", "-p", "-t", sess, "-S", "-40"], text=True)
    except Exception:
        continue

    tail = "\n".join(pane.splitlines()[-18:])

    # Always dismiss an open RC dialog with Escape (never Enter)
    if "Enter to select · Esc to continue" in tail and ("Remote Control" in tail or "Disconnect this session" in tail):
        subprocess.run(["tmux", "send-keys", "-t", sess, "Escape"], check=False)
        log_event(sess, "B", "DISMISSED_RC_DIALOG_ESCAPE")
        continue

    # Case C: Seat is broken at a blocking login error -> respawn with 1-year token (becomes Case A)
    has_login_err = any(err in tail for err in (
        "Not logged in",
        "Please run /login",
        "OAuth token has expired",
    ))
    if has_login_err:
        if not is_idle_strict(tail):
            log_event(sess, "C", "SKIP_BUSY")
            continue
        own_uuid = find_own_uuid(sess, pool, tree_pids)
        if not own_uuid:
            log_event(sess, "C", "SKIP_NO_OWN_TRANSCRIPT")
            continue
        other_holders = [p for p in held_uuids.get(own_uuid, []) if p not in tree_pids]
        if other_holders:
            log_event(sess, "C", f"SKIP_UUID_HELD_BY_OTHER:{other_holders}")
            continue
        token_file = f"/home/mboyle/.claude-{pool}/token-1year.txt"
        if not os.path.exists(token_file):
            log_event(sess, "C", "SKIP_MISSING_1YEAR_TOKEN")
            continue
        cmd = (
            f"cd {cwd} && "
            f"export CLAUDE_CONFIG_DIR=/home/mboyle/.claude-{pool} "
            f"CLAUDE_CODE_OAUTH_TOKEN=\"$(cat /home/mboyle/.claude-{pool}/token-1year.txt)\"; "
            f"exec /home/mboyle/.local/bin/claude --dangerously-skip-permissions --resume {own_uuid}"
        )
        subprocess.run(["tmux", "respawn-pane", "-k", "-t", sess, cmd], check=False)
        log_event(sess, "C", f"RESPAWNED_1YEAR_TOKEN:{own_uuid}")
        continue

    # Case A: Seat process HAS CLAUDE_CODE_OAUTH_TOKEN in /proc/<pid>/environ -> NO typing
    if has_oauth_token_env(tree_pids):
        continue

    # Case B: Seat process has NO token env (full .credentials.json login) -> RC when possible
    if "Remote Control active" in pane or "Remote Control connecting" in pane or "Remote Control requires a full-scope" in pane or "Remote Control disconnected" in pane:
        continue
    if sess in attempted_rc:
        continue
    if not is_idle_strict(tail):
        continue

    # Type /remote-control on strictly idle full-login seat, wait 2.5s, and dismiss dialog with Escape if opened
    subprocess.run(["tmux", "send-keys", "-t", sess, "/remote-control", "Enter"], check=False)
    time.sleep(2.5)
    try:
        pane2 = subprocess.check_output(["tmux", "capture-pane", "-p", "-t", sess, "-S", "-25"], text=True)
        if "Enter to select · Esc to continue" in pane2:
            subprocess.run(["tmux", "send-keys", "-t", sess, "Escape"], check=False)
    except Exception:
        pass
    attempted_rc.add(sess)
    try:
        with open(attempted_rc_path, "a") as af:
            af.write(sess + "\n")
    except Exception:
        pass
    log_event(sess, "B", "TYPED_RC_FULL_LOGIN_IDLE")
"""


def check_host(h):
    try:
        if h == "127.0.0.1":
            r = subprocess.run(
                ["python3", "-c", REMOTE_SCRIPT],
                capture_output=True,
                text=True,
                timeout=20,
            )
        else:
            r = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "ConnectTimeout=4",
                    "-o",
                    "StrictHostKeyChecking=no",
                    h,
                    "python3 -",
                ],
                input=REMOTE_SCRIPT,
                capture_output=True,
                text=True,
                timeout=25,
            )
        return (h, [l for l in r.stdout.strip().splitlines() if l.strip()])
    except Exception as e:
        return (h, [f"ERR:{e}"])


def main():
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines_out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=14) as ex:
        for h, res in ex.map(check_host, HOSTS):
            for item in res:
                entry = f"{ts}\t{h}\t{item}"
                lines_out.append(entry)
                print(f"  {h}: {item}")
    if lines_out:
        with open(LOG_PATH, "a") as lf:
            for l in lines_out:
                lf.write(l + "\n")
    else:
        print(f"[{ts}] bd-rc-enforcer: 0 actions needed across {len(HOSTS)} hosts.")


if __name__ == "__main__":
    main()
