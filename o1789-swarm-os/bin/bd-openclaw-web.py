#!/usr/bin/env python3
"""
Boylenet OpenClaw Web Synchronizer & Parity Auditor (`bd-openclaw-web.py`, `:4097`)
Ensures `/home/mboyle/.openclaw/openclaw.json`, `/home/mboyle/.openclaw-dev/openclaw.json`,
and workspace `AGENTS.md` expose:
  1. `🟢 LOCAL` vs `☁️ CLOUD` model labels across all 86+ Local Vault & 8 Cloud Burst models
  2. `:4079` 50-Toolkit OpenAPI specs (`/openapi.json`, `/web-osint/openapi.json`, `/data-science/openapi.json`, `/devops-infra/openapi.json`, `/media-ai/openapi.json`)
  3. `BD KB` search (`http://10.0.70.164:4079/api/tool/bd_kb_search` & Qdrant `bd_master_kb`)
  4. `🛡️ Airgap` status badge (`LOCAL-FIRST ($0.00) • WAN ACTIVE`)
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import urllib.request

OPENCLAW_MAIN = Path("/home/mboyle/.openclaw/openclaw.json")
OPENCLAW_DEV = Path("/home/mboyle/.openclaw-dev/openclaw.json")
OPENCLAW_DEV_LAST = Path("/home/mboyle/.openclaw-dev/openclaw.json.last-good")

CLOUD_MODELS = [
    {"id": "cloud/claude-opus-4-7", "name": "☁️ CLOUD • Anthropic Claude Opus 4.7 ($1,000 Cloud Burst)"},
    {"id": "cloud/claude-sonnet-4-6", "name": "☁️ CLOUD • Anthropic Claude Sonnet 4.6 ($1,000 Cloud Burst)"},
    {"id": "cloud/gpt-5.4-pro", "name": "☁️ CLOUD • OpenAI GPT-5.4 Pro ($1,000 Cloud Burst)"},
    {"id": "cloud/gemini-3.1-pro", "name": "☁️ CLOUD • Google Gemini 3.1 Pro ($1,000 Cloud Burst)"},
    {"id": "cloud/grok-4.20-max", "name": "☁️ CLOUD • xAI Grok 4.20 Max ($1,000 Cloud Burst)"},
    {"id": "cloud/deepseek-v4-cloud", "name": "☁️ CLOUD • DeepSeek-V4 Cloud API ($1,000 Cloud Burst)"},
    {"id": "cloud/kimi-k2.5-cloud", "name": "☁️ CLOUD • Moonshot Kimi-K2.5 Cloud ($1,000 Cloud Burst)"},
    {"id": "cloud/qwen3-max-cloud", "name": "☁️ CLOUD • Alibaba Qwen3-Max Cloud ($1,000 Cloud Burst)"},
]

AGENTS_MD_CONTENT = """# 🛡️ OpenClaw (:4097) • Boylenet 50-Toolkit, BD KB & Airgap Workspace
- **🛡️ Airgap Status Badge**: `LOCAL-FIRST ($0.00) • WAN ACTIVE` (`POST http://10.0.70.164:4079/api/tool/airgap_and_cluster_status`)
- **📚 BD KB Search**: `POST http://10.0.70.164:4079/api/tool/bd_kb_search` (`{"query":"...", "top_k":5}`) + Qdrant `http://10.0.70.125:6333/collections/bd_master_kb`
- **🛠️ :4079 50-Toolkit OpenAPI Specs**:
  - `http://10.0.70.164:4079/openapi.json` (All 50 Toolkits)
  - `http://10.0.70.164:4079/web-osint/openapi.json`
  - `http://10.0.70.164:4079/data-science/openapi.json`
  - `http://10.0.70.164:4079/devops-infra/openapi.json`
  - `http://10.0.70.164:4079/media-ai/openapi.json`
- **🟢 LOCAL vs ☁️ CLOUD Models**: 87 `🟢 LOCAL` models on `.72`/`.83`/`.125`/`.137` + 8 `☁️ CLOUD` burst models via `:4000`.
"""


def sync_openclaw() -> dict:
    cfg = json.loads(OPENCLAW_MAIN.read_text(encoding="utf-8"))
    providers = cfg.setdefault("models", {}).setdefault("providers", {})

    local_count = 0
    cloud_count = 0

    for pname, pval in providers.items():
        mlist = pval.get("models", []) if isinstance(pval, dict) else []
        for mobj in mlist:
            if not isinstance(mobj, dict):
                continue
            mid = str(mobj.get("id", "")).strip()
            raw_name = str(mobj.get("name", mid)).strip()
            clean_name = (
                raw_name.replace("🟢 LOCAL • ", "")
                .replace("☁️ CLOUD • ", "")
                .replace("🟢 LOCAL ", "")
                .replace("☁️ CLOUD ", "")
                .strip()
            )
            if mid.startswith("cloud/") or "CLOUD" in raw_name:
                mobj["name"] = f"☁️ CLOUD • {clean_name}"
                cloud_count += 1
            else:
                mobj["name"] = f"🟢 LOCAL • {clean_name}"
                local_count += 1

    litellm_models = providers.setdefault("boylenet-litellm", {}).setdefault("models", [])
    existing_ids = {m.get("id") for m in litellm_models if isinstance(m, dict)}
    for cm in CLOUD_MODELS:
        if cm["id"] not in existing_ids:
            litellm_models.append(
                {
                    "id": cm["id"],
                    "name": cm["name"],
                    "api": "openai-completions",
                    "reasoning": True,
                    "contextWindow": 200000,
                    "maxTokens": 16384,
                }
            )
            cloud_count += 1

    also_allow = cfg.setdefault("tools", {}).setdefault("alsoAllow", [])
    for extra_tool in (
        "bd_kb_search",
        "qdrant_rag_search",
        "airgap_and_cluster_status",
        "openapi_50_toolkits_4079",
        "subagent_swarm_dispatch",
        "boylenet_doctor_and_self_healer",
    ):
        if extra_tool not in also_allow:
            also_allow.append(extra_tool)

    OPENCLAW_MAIN.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Sync to ~/.openclaw-dev so `openclaw --dev` on :4097 serves the full 86+8 catalog
    if OPENCLAW_DEV.parent.exists():
        dev_cfg = json.loads(json.dumps(cfg))
        dev_cfg.setdefault("agents", {}).setdefault("defaults", {})["workspace"] = (
            "/home/mboyle/.openclaw-dev/workspace"
        )
        OPENCLAW_DEV.write_text(
            json.dumps(dev_cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        shutil.copyfile(OPENCLAW_DEV, OPENCLAW_DEV_LAST)

    for ws_dir in (
        Path("/home/mboyle/.openclaw/workspace"),
        Path("/home/mboyle/.openclaw-dev/workspace"),
    ):
        ws_dir.mkdir(parents=True, exist_ok=True)
        (ws_dir / "AGENTS.md").write_text(AGENTS_MD_CONTENT, encoding="utf-8")

    http_status = 0
    try:
        with urllib.request.urlopen("http://127.0.0.1:4097/", timeout=5) as r:
            http_status = r.status
    except Exception:
        pass

    return {
        "ok": True,
        "service": "bd-openclaw-web (:4097)",
        "main_config": str(OPENCLAW_MAIN),
        "dev_config": str(OPENCLAW_DEV),
        "local_models_labeled": local_count,
        "cloud_models_labeled": cloud_count,
        "http_4097_status": http_status,
        "airgap_badge": "🛡️ Airgap: LOCAL-FIRST ($0.00) • WAN ACTIVE",
        "gateway_4079_openapi": "http://10.0.70.164:4079/openapi.json",
        "bd_kb_endpoint": "http://10.0.70.164:4079/api/tool/bd_kb_search",
    }


if __name__ == "__main__":
    print(json.dumps(sync_openclaw(), indent=2))
