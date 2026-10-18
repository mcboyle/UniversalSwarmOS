---
name: boylenet-bdkb-hivemind
description: Sub-20ms 6-Volume Boylenet Master Knowledge Base (BD KB), Qdrant bd_master_kb (10.0.70.125:6333), and HiveMind episodic memory recall/publish skill for Kimi K2.8, Claude Code, Codex, and AGY.
---

# Boylenet 6-Volume `BD KB` & HiveMind Memory (`boylenet-bdkb-hivemind`)

Provides `<20ms` hybrid semantic + lexical search across all 6 canonical volumes of the Boylenet Master Knowledge Base (`/home/mboyle/bd-persist/bd-kb/01..06*.md`), Qdrant `bd_master_kb` (`10.0.70.125:6333` with 1024-d `BAAI/bge-m3` embeddings on `.137:8091`), and HiveMind episodic memory (`hivemind_recall` / `hivemind_store`).

## 1. The 6 Canonical `BD KB` Volumes
1. `01-BOYLENET-INFRASTRUCTURE-AND-27VM-TOPOLOGY.md`
2. `02-LOCAL-AI-MODELS-VRAM-AND-BENCHMARKS.md`
3. `03-WEB-PORTALS-COCKPITS-AND-STUDIOS.md`
4. `04-FLEET-LAWS-DYNAMIC-ROUTING-AND-OPERATIONS.md`
5. `05-OPENWEBUI-PIPELINES-TOOLS-AND-SKILLS.md`
6. `06-BULKDOWNLOADER-ARCHITECTURE-AND-CI-TAXONOMY.md`

## 2. Sub-20ms Query & Sync Commands

### Query 6-Volume `BD KB` + Qdrant `bd_master_kb` (`<20ms`)
```bash
python3 -c '
import json, sys, time
sys.path.insert(0, "/home/mboyle/bin")
import bd_openwebui_pipelines_bdkb_ext as bdkb
t0 = time.perf_counter()
res = bdkb.tool_bd_kb_search({"query": " ".join(sys.argv[1:]) or "27-VM topology and O1740 routing", "top_k": 5})
res["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
print(json.dumps(res, indent=2))
' "O1740 dynamic routing"
```

### Recall Verified Episodes from HiveMind Memory
```bash
python3 /home/mboyle/bin/bd-local-mcp-bridge.py --call hivemind_recall --args '{"query":"pytest setup error classification","limit":5}'
```

### Store New Verified Lesson in HiveMind Memory
```bash
python3 /home/mboyle/bin/bd-local-mcp-bridge.py --call hivemind_store --args '{"title":"Verified pattern","content":"Root cause and fix receipt","tags":["fleet","verified"]}'
```

### Trigger Live `BD KB` Re-Index to Qdrant (`bd_master_kb`)
```bash
python3 /home/mboyle/bin/bd-kb-live-sync.py --once
```
