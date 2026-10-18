#!/usr/bin/env python3
"""
Boylenet OpenCode Web Synchronizer & Parity Auditor (`bd-opencode-web.py`, `:4096`)
Ensures `/home/mboyle/.config/opencode/opencode.json` and `:4096` expose:
  1. `🟢 LOCAL` vs `☁️ CLOUD` model labels across all 86+ Local Vault & 8 Cloud Burst models
  2. `:4079` 50-Toolkit OpenAPI specs (`/openapi.json`, `/web-osint/openapi.json`, `/data-science/openapi.json`, `/devops-infra/openapi.json`, `/media-ai/openapi.json`)
  3. `BD KB` search (`http://10.0.70.164:4079/api/tool/bd_kb_search` & Qdrant `bd_master_kb`)
  4. `🛡️ Airgap` status badge (`LOCAL-FIRST ($0.00) • WAN ACTIVE`)
"""

from __future__ import annotations

import json
from pathlib import Path
import urllib.request

OPENCODE_CFG = Path("/home/mboyle/.config/opencode/opencode.json")
OPENCODE_KB_MD = Path("/home/mboyle/.config/opencode/BOYLENET-4079-50TOOLS-BDKB.md")

CLOUD_MODELS = {
    "cloud/claude-opus-4-7": "☁️ CLOUD • Anthropic Claude Opus 4.7 ($1,000 Cloud Burst)",
    "cloud/claude-sonnet-4-6": "☁️ CLOUD • Anthropic Claude Sonnet 4.6 ($1,000 Cloud Burst)",
    "cloud/gpt-5.4-pro": "☁️ CLOUD • OpenAI GPT-5.4 Pro ($1,000 Cloud Burst)",
    "cloud/gemini-3.1-pro": "☁️ CLOUD • Google Gemini 3.1 Pro ($1,000 Cloud Burst)",
    "cloud/grok-4.20-max": "☁️ CLOUD • xAI Grok 4.20 Max ($1,000 Cloud Burst)",
    "cloud/deepseek-v4-cloud": "☁️ CLOUD • DeepSeek-V4 Cloud API ($1,000 Cloud Burst)",
    "cloud/kimi-k2.5-cloud": "☁️ CLOUD • Moonshot Kimi-K2.5 Cloud ($1,000 Cloud Burst)",
    "cloud/qwen3-max-cloud": "☁️ CLOUD • Alibaba Qwen3-Max Cloud ($1,000 Cloud Burst)",
}

KB_INSTRUCTIONS_MD = """# 🛡️ Boylenet OpenCode (:4096) • :4079 50-Toolkit, BD KB & Airgap Parity
- **🛡️ Airgap Status Badge**: `LOCAL-FIRST ($0.00) • WAN ACTIVE` (`POST http://10.0.70.164:4079/api/tool/airgap_and_cluster_status`)
- **📚 BD KB Instant Search**: `POST http://10.0.70.164:4079/api/tool/bd_kb_search` (`{"query":"...", "top_k":5}`) + Qdrant `http://10.0.70.125:6333/collections/bd_master_kb`
- **🛠️ :4079 50-Toolkit OpenAPI Specs**:
  - Master 50-Toolkit OpenAPI: `http://10.0.70.164:4079/openapi.json`
  - Web & OSINT Suite: `http://10.0.70.164:4079/web-osint/openapi.json`
  - Data Science & BD KB Suite: `http://10.0.70.164:4079/data-science/openapi.json`
  - DevOps, 27-Node SSH & vSAN Suite: `http://10.0.70.164:4079/devops-infra/openapi.json`
  - Media, FLUX Image & Voice Suite: `http://10.0.70.164:4079/media-ai/openapi.json`
- **🟢 LOCAL vs ☁️ CLOUD Model Labels**: All local vault models are prefixed with `🟢 LOCAL •` and all cloud burst models are prefixed with `☁️ CLOUD •`.
"""


def sync_opencode() -> dict:
    OPENCODE_CFG.parent.mkdir(parents=True, exist_ok=True)
    OPENCODE_KB_MD.write_text(KB_INSTRUCTIONS_MD, encoding="utf-8")

    cfg = json.loads(OPENCODE_CFG.read_text(encoding="utf-8"))
    providers = cfg.setdefault("provider", {})

    local_count = 0
    cloud_count = 0

    for pname, pval in providers.items():
        if isinstance(pval, dict) and "name" in pval:
            if "🛡️ Airgap" not in pval["name"]:
                pval["name"] = f"{pval['name']} • 🛡️ Airgap Ready • 🛠️ :4079 50-Tools & 📚 BD KB"
        models = pval.get("models", {}) if isinstance(pval, dict) else {}
        for mid, mobj in list(models.items()):
            if not isinstance(mobj, dict):
                continue
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

    litellm_models = providers.setdefault("boylenet-litellm", {}).setdefault("models", {})
    for cid, cname in CLOUD_MODELS.items():
        if cid not in litellm_models:
            litellm_models[cid] = {
                "name": cname,
                "limit": {"context": 200000, "output": 16384},
            }
            cloud_count += 1
        else:
            litellm_models[cid]["name"] = cname

    instructions = cfg.setdefault("instructions", [])
    if str(OPENCODE_KB_MD) not in instructions:
        instructions.append(str(OPENCODE_KB_MD))

    OPENCODE_CFG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Verify live :4096 endpoint
    http_status = 0
    try:
        with urllib.request.urlopen("http://127.0.0.1:4096/config", timeout=5) as r:
            http_status = r.status
    except Exception:
        pass

    return {
        "ok": True,
        "service": "bd-opencode-web (:4096)",
        "config_path": str(OPENCODE_CFG),
        "instructions_path": str(OPENCODE_KB_MD),
        "local_models_labeled": local_count,
        "cloud_models_labeled": cloud_count,
        "http_4096_config_status": http_status,
        "airgap_badge": "🛡️ Airgap: LOCAL-FIRST ($0.00) • WAN ACTIVE",
        "gateway_4079_openapi": "http://10.0.70.164:4079/openapi.json",
        "bd_kb_endpoint": "http://10.0.70.164:4079/api/tool/bd_kb_search",
    }


if __name__ == "__main__":
    print(json.dumps(sync_opencode(), indent=2))
