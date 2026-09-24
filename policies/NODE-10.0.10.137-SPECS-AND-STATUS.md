# Node Ingestion Report: BattleStation (`10.0.10.137`)

## 1. Hardware Specifications

| Component | Specification | Details |
|---|---|---|
| **Hostname** | `BattleStation` | Workstation Subnet (`10.0.10.137`) |
| **Operating System** | Windows 11 Pro | Build 10.0.26200 (64-bit) |
| **CPU** | AMD Ryzen 9 3900X | 12 Physical Cores, 24 Logical Threads |
| **GPU** | NVIDIA GeForce RTX 2080 Ti | 11 GB GDDR6 VRAM (11,264 MiB), Driver 610.47, CUDA 13.3 |
| **Memory (RAM)** | 32 GB Physical | 33,473,120 KB total (~16 GB free) |
| **Storage** | 476 GB NVMe SSD | C: Drive (108.4 GB free space) |

---

## 2. Remote Access & Automation Channels

1. **Native OpenSSH**:
   - **Port**: `22`
   - **Authentication**: Passwordless Ed25519 public key (`mboyle@test4`)
   - **Status**: Verified active. Native execution via `ssh Administrator@10.0.10.137`.
2. **WinRM Remote PowerShell**:
   - **Port**: `5985` (HTTP)
   - **Network Category**: Private
   - **Authentication**: NTLM (`Administrator:Matt99!!`)
   - **Status**: Verified active. Sub-second execution from controller `test5`.
3. **SMB / RPC Execution**:
   - **Port**: `445`
   - **Protocol**: SMBv3.0 dialect
   - **Tools**: `atexec.py`, `smbexec.py` in `/home/mboyle/.venv_fleet_mgmt/bin/`
4. **Chrome DevTools Protocol (CDP)**:
   - **Port**: `9222` (Portproxy forwarding `0.0.0.0:9222 -> [::1]:9222`)
   - **Flags**: `--remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="C:\ChromeDebugProfile"`
   - **Status**: Live and verified. Browser windows open on desktop with Gemini, Claude A, Claude B, and ChatGPT tabs.

---

## 3. Active 4-Way Oracle Targets on 10.0.10.137

| Target | Model Tier | User Profile | Status |
|---|---|---|---|
| `claude-a` | Claude Opus 5.5 | Matthew Boyle · Max | Verified Live |
| `claude-b` | Claude Fable 5.1 | Matthew · Max | Verified Live |
| `chatgpt` | ChatGPT Pro | matthew boyle Pro | Verified Live |
| `gemini` | Gemini Pro | matthew | Verified Live |

---

## 4. Verification Proofs
- **Single Target**: `bd-oracle --node 137 --oracle claude-b "State the capital of Germany in one word."` -> `Berlin`
- **4-Way Fanout**: `bd-oracle --node 137 --oracle all --json "What is 100 - 35? Return only the number."` -> All returned `65`
- **Consensus Matrix**: `bd-oracle --node 137 --oracle all --consensus --json "Is the Earth flat? Answer strictly with the word PASS or REJECT."` -> `REJECT` (4/4 unanimous supermajority)
- **Visual Artifacts**:
  - Claude A: [`/home/mboyle/bd-persist/node137-ready-claude-a.png`](file:///home/mboyle/bd-persist/node137-ready-claude-a.png)
  - Claude B: [`/home/mboyle/bd-persist/node137-ready-claude-b.png`](file:///home/mboyle/bd-persist/node137-ready-claude-b.png)
  - ChatGPT: [`/home/mboyle/bd-persist/node137-ready-chatgpt.png`](file:///home/mboyle/bd-persist/node137-ready-chatgpt.png)
  - Gemini: [`/home/mboyle/bd-persist/node137-ready-gemini.png`](file:///home/mboyle/bd-persist/node137-ready-gemini.png)
