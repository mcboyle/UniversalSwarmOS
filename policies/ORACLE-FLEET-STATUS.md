# Virtual Browser Oracle Fleet Status & Dual-Node Bridge

- **Primary VM Node**: `Bittorrent` (`10.0.70.181:9222`)
- **GPU Workstation Node**: `BattleStation` (`10.0.10.137:9222`)
- **CLI Driver**: [`/home/mboyle/bin/bd-oracle`](file:///home/mboyle/bin/bd-oracle) (Supports `--node 181` and `--node 137`)

---

## 1. Multi-Node Deployment Matrix

| Node | Host IP | Specs | Active Oracles | Remote Automation |
|---|---|---|---|---|
| **Node 1 (VM)** | `10.0.70.181` | 32 vCPUs, 128 GB RAM | Gemini Ultra, ChatGPT Plus, Claude A, Claude B | govc, CDP bridge |
| **Node 2 (GPU)** | `10.0.10.137` | Ryzen 3900X (24T), RTX 2080 Ti (11GB), 32GB RAM | Gemini Pro, ChatGPT Pro, Claude A, Claude B | Passwordless OpenSSH, WinRM, CDP |

---

## 2. CLI Usage Examples

```bash
# Query BattleStation (Node 137) specifically
bd-oracle --node 137 --oracle claude-b "State the capital of Germany in one word."

# 4-way fanout on BattleStation
bd-oracle --node 137 --oracle all --json "What is 100 - 35? Return only the number."

# Cross-model consensus matrix on BattleStation
bd-oracle --node 137 --oracle all --consensus --json "Is the Earth flat? Answer strictly with the word PASS or REJECT."

# Query VM Node 181 specifically
bd-oracle --node 181 --oracle gemini "What is 77 * 88?"
```

---

## 3. Visual Artifacts
- **Node 137**:
  - Claude A: [`/home/mboyle/bd-persist/node137-ready-claude-a.png`](file:///home/mboyle/bd-persist/node137-ready-claude-a.png)
  - Claude B: [`/home/mboyle/bd-persist/node137-ready-claude-b.png`](file:///home/mboyle/bd-persist/node137-ready-claude-b.png)
  - ChatGPT: [`/home/mboyle/bd-persist/node137-ready-chatgpt.png`](file:///home/mboyle/bd-persist/node137-ready-chatgpt.png)
  - Gemini: [`/home/mboyle/bd-persist/node137-ready-gemini.png`](file:///home/mboyle/bd-persist/node137-ready-gemini.png)
- **Node 181**:
  - Claude B: [`/home/mboyle/bd-persist/claude-b-response.png`](file:///home/mboyle/bd-persist/claude-b-response.png)
  - Claude A: [`/home/mboyle/bd-persist/claude-a-chat.png`](file:///home/mboyle/bd-persist/claude-a-chat.png)
  - Gemini Ultra: [`/home/mboyle/bd-persist/gemini-operational-success.png`](file:///home/mboyle/bd-persist/gemini-operational-success.png)
