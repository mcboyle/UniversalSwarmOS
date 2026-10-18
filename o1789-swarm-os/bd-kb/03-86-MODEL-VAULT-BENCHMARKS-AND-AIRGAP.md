# 🧠 BD-KB 3: 86-Model AI Vault (`8.9 TB` on `.72` & `.83`), Benchmarks (`pp512`/`tg128`), Category Winners, `bd-airgap` & `bd-raw-ai`

- **Document ID**: `bd-kb-03-86-models`
- **Canonical Path**: `/home/mboyle/bd-persist/bd-kb/03-86-MODEL-VAULT-BENCHMARKS-AND-AIRGAP.md`
- **Source Authority**: `/home/mboyle/bd-persist/harness-work/O1789/infra-upgrade/AGENT37-NEW-FRONTIER-MODELS-BENCHMARK-RECEIPTS.md` & `AGENT95-86-MODELS-ALL-PLATFORMS-OPENWEBUI-LITELLM-RECEIPTS.md`

---

## 1. Local AI Vault Architecture (`8.9+ TB` Across `.72` & `.83`)

The Boylenet Local AI Vault stores **86 distinct local AI model families** (`10.5 TB` raw / `8.9+ TB` deduplicated weights) across two 562 GiB DDR4 + NVIDIA Tesla T4 (`16 GB` VRAM) vault servers:
- **Vault A (`10.0.70.72` `ai-srv01`)**: `/mnt/models_hot` (`5.1 TB`, 47 model directories).
- **Vault B (`10.0.70.83` `ai-srv02`)**: `/mnt/models_hot` (`5.4 TB`, 39 model directories).
- **Inference Engine**: `llama.cpp` build `b11716` compiled with CUDA 12.x (`libggml-cuda.so` for 4x NVIDIA Tesla T4 `sm_75`) + Intel Skylake-X AVX-512 (`libggml-cpu-skylakex.so`) + MoE expert CPU offload (`-ot ".ffn_.*_exps.=CPU"`).
- **OpenWebUI Naming Convention**: Every model in OpenWebUI (`:8090` and `:8080`) carries an explicit `[LOCAL • ...]` or `[CLOUD • ...]` prefix so operators can immediately verify whether a prompt runs 100% air-gapped on Boylenet hardware or routes to an external cloud API.

---

## 2. Category Winners & Flagship Benchmark Leaderboard (`llama-bench` `b11716`)

| Category | Winner Model | Node(s) | Size (`GiB`) | Hardware Pool & Flags | Prefill (`pp512`) | Decode (`tg128`) |
|---|---|---|---:|---|---:|---:|
| **🏆 #1 Fast Coding & Tool Use (`tg128`)** | `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` | `.72+.83` | `17.28 GiB` | 2x Tesla T4 (`32 GB` VRAM, `-ngl 999 -fa 1`) | **`848.90 tok/s`** | **`77.62 tok/s`** |
| **🥈 #2 High-Precision Coding (`Q6_K`)** | `Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf` | `.72+.83` | `23.37 GiB` | 2x Tesla T4 (`32 GB` VRAM, `-ngl 999 -fa 1`) | **`710.50 tok/s`** | **`64.20 tok/s`** |
| **🛡️ #1 Offensive Security & Red-Team** | `Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K_M.gguf` | `.72+.83` | `20.22 GiB` | 2x Tesla T4 (`32 GB` VRAM, `-ngl 999 -fa 1`) | **`799.00 tok/s`** | **`66.47 tok/s`** |
| **⚡ #1 Single-GPU Prefill Speed (`pp512`)** | `Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf` | `.72` / `.83` | `9.11 GiB` | 1x Tesla T4 (`16 GB` VRAM, `-ngl 999 -fa 1`) | **`1,005.86 tok/s`** | **`21.39 tok/s`** |
| **🚀 #1 Single-GPU MoE Decode (`tg128`)** | `Occamy-1.0.APEX-I-MiniPlus-V2.1-Abliterated.gguf` | `.83` | `13.65 GiB` | 1x Tesla T4 (`16 GB` VRAM, `-ngl 999 -fa 1`) | **`638.35 tok/s`** | **`50.98 tok/s`** |
| **🔍 #1 Speculative Drafter** | `dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf` | `.72` / `.83` | `10.15 GiB` | 1x Tesla T4 (`--model-draft`) | **`680.20 tok/s`** | **`61.50 tok/s`** |
| **🧠 #1 Claude-Opus Distilled MoE (`35B.A3B`)** | `huihui-qwen3.6-35b-a3b-claude-4.7-opus-abliterated-q4_k_m.gguf` | `.83` | `19.71 GiB` | 2x Tesla T4 (`795.0` / `65.8`) or 1xT4+AVX512 (`78.96` / `22.81`) | **`795.00 tok/s`** | **`65.80 tok/s`** |
| **👁️ #1 Multimodal Vision-Language (`35B.A3B`)** | `MiniCPM-V-4_7-35B-A3B-Q4_K_M.gguf` | `.83` | `19.71 GiB` | 1x Tesla T4 + Skylake AVX-512 (`-ot exps=CPU`) | **`79.71 tok/s`** | **`23.14 tok/s`** |
| **🔐 #1 Captcha & Visual Security (`9B`)** | `CaptchaKraken-v1.2-Q4_K_M.gguf` | `.72` | `14.97 GiB` | 1x Tesla T4 (`16 GB` VRAM, `-ngl 99 -fa 1`) | **`958.05 tok/s`** | **`28.21 tok/s`** |
| **🏛️ #1 70B Pure-VRAM Reasoning** | `DeepSeek-R1-Distill-Llama-70B-IQ4_XS.gguf` | `.72` | `35.30 GiB` | 4x Tesla T4 (`64 GB` Pure VRAM, 81/81 GPU layers) | **`121.83 tok/s`** | **`3.90 tok/s`** |
| **🌐 #1 100B–200B Frontier Hybrid** | `DeepSeek-V4-Flash-Q4_K-0731.gguf` | `.72`, `.83` | `153.33 GiB` | 4x Tesla T4 + Skylake AVX-512 (`--numa distribute -t 48`) | **`142.37 tok/s`** | **`14.20 tok/s`** |
| **🌌 #1 1-Trillion Parameter Behemoth** | `KIMI-K3-MXP4-DERISKED-Q2_K` (`38` shards) | `.72` | `940.18 GiB` | 4-Node `1.73 TB` DDR4 + 4x Tesla T4 Hybrid | **`69.13 tok/s`** | **`16.30 tok/s`** |

---

## 3. Complete 55 GGUF Benchmark Reference (`pp512` & `tg128`)

| # | Vault Directory | GGUF Model | Node | Size (`GiB`) | `pp512` | `tg128` |
|---:|---|---|---|---:|---:|---:|
| 1 | `qwythos-9b` | `Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf` | `.72`, `.83` | `9.11` | `1,005.86 tok/s` | `21.39 tok/s` |
| 2 | `qwythos-9b` | `Qwythos-9B-Claude-Mythos-5-1M-MTP-BF16.gguf` | `.72` | `17.14` | `224.00 tok/s` | `16.28 tok/s` |
| 3 | `tier1-qwen3-coder-30b-a3b` | `Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf` | `.72` | `17.28` | `848.90 tok/s` | `77.62 tok/s` |
| 4 | `tier1-qwen3-coder-30b-a3b` | `Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf` | `.72` | `23.37` | `710.50 tok/s` | `64.20 tok/s` |
| 5 | `cyberstrike-35b` | `Huihui-CyberStrike-OffSec-35B-abliterated-Q4_K_M.gguf` | `.72`, `.125` | `20.22` | `799.00 tok/s` | `66.47 tok/s` |
| 6 | `tier1-fast` | `Qwen2.5-Coder-32B-Instruct-Q4_K_M.gguf` | `.125`, `.228` | `18.48` | `266.51 tok/s` | `11.27 tok/s` |
| 7 | `qwythos-27b` | `Qwythos-27B-Claude-Mythos-5-MTP-Q4_K_M.gguf` | `.72` | `16.39` | `289.31 tok/s` | `12.30 tok/s` |
| 8 | `deepseek-v4-flash` | `dspark-DeepSeek-V4-Flash-0731-Q8_0.gguf` | `.72`, `.83` | `10.15` | `680.20 tok/s` | `61.50 tok/s` |
| 9 | `deepseek-v4-flash` | `dspark-DeepSeek-V4-Flash-0731-BF16.gguf` | `.72`, `.83` | `10.54` | `612.40 tok/s` | `54.20 tok/s` |
| 10 | `qwythos-27b` | `Qwythos-27B-Claude-Mythos-5-MTP-Q8_0.gguf` | `.72` | `27.05` | `316.53 tok/s` | `8.13 tok/s` |
| 11 | `qwythos-27b` | `Qwythos-27B-Claude-Mythos-5-MTP-BF16.gguf` | `.72` | `51.77` | `94.50 tok/s` | `4.48 tok/s` |
| 12 | `cyberstrike-35b` | `Huihui-CyberStrike-OffSec-35B-abliterated-bf16.gguf` | `.72` | `67.03` | `184.00 tok/s` | `19.72 tok/s` |
| 13 | `deepseek-r1-70b-abliterated` | `DeepSeek-R1-Distill-Llama-70B-IQ4_XS.gguf` | `.72` | `35.30` | `121.83 tok/s` | `3.90 tok/s` |
| 14 | `tier2-70b` | `DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf` | `.72` | `39.60` | `107.80 tok/s` | `3.61 tok/s` |
| 15 | `llama-3.3-70b-abliterated` | `Llama-3.3-70B-Instruct-Q4_K_M.gguf` | `.72` | `39.60` | `108.22 tok/s` | `3.59 tok/s` |
| 16 | `qwen3.8-flash-next` | `Swift-Qwen3.8-Flash-Next-GSQ-RCO-IQ2_XS` | `.72` | `63.47` | `120.58 tok/s` | `14.11 tok/s` |
| 17 | `qwen3.8-flash-next` | `Qwen3.8-Flash-Next-UD-IQ4_XS` | `.72` | `87.25` | `98.40 tok/s` | `11.40 tok/s` |
| 18 | `deepseek-v4-flash` | `DeepSeek-V4-Flash-Q2-0731.gguf` | `.83` | `80.76` | `47.28 tok/s` | `18.40 tok/s` |
| 19 | `deepseek-v4-flash` | `DeepSeek-V4-Flash-Q4_K-0731.gguf` | `.72`, `.83` | `153.33` | `142.37 tok/s` | `14.20 tok/s` |
| 20 | `tier3a-qwen3-235b-a22b` | `Qwen3-235B-A22B-Instruct-2507-Q4_K_M` | `.83` | `132.39` | `118.50 tok/s` | `6.40 tok/s` |
| 21 | `glm-5.2` | `GLM-5.2-UD-IQ2_XXS_RoutedIQ2XXS_blk78Q2K` | `.83` | `196.57` | `8.76 tok/s` | `2.21 tok/s` |
| 22 | `kimi-k3-abliterated-q2k-gguf` | `KIMI-K3-MXP4-DERISKED-Q2_K` | `.72` | `940.18` | `69.13 tok/s` | `16.30 tok/s` |
| 23 | `moss-music-8b-instruct-gguf` | `moss-lm-q8_0.gguf` | `.83` | `8.11` | `135.25 tok/s` | `20.34 tok/s` |
| 24 | `occamy-1.0-35b-abliterated` | `Occamy-1.0.APEX-I-MiniPlus-V2.1-Abliterated.gguf` | `.83` | `13.65` | `638.35 tok/s` | `50.98 tok/s` |
| 25 | `lfm2.5-24b-a2b-uncensored` | `LFM2.5-24B-A2B-Uncensored-AD-Q4_K_M.gguf` | `.72` | `14.30` | `172.71 tok/s` | `20.52 tok/s` |
| 26 | `captchakraken-v1.2-gguf` | `CaptchaKraken-v1.2-Q4_K_M.gguf` | `.72` | `14.97` | `958.05 tok/s` | `28.21 tok/s` |
| 27 | `gemma-4-26b-a4b-uncensored` | `gemma-4-26B-A4B-it-uncensored-Q4_K_M.gguf` | `.72` | `15.64` | `178.18 tok/s` | `21.57 tok/s` |
| 30 | `cyberstag-security-26b-a4b-heretic` | `CyberStag-Security-26B-A4B-V1-Uncensored-Heretic-UD-Q4_K_XL.gguf` | `.72` | `15.84` | `200.81 tok/s` | `21.93 tok/s` |
| 36 | `qwen3.6-35b-claude-opus-abliterated` | `huihui-qwen3.6-35b-a3b-claude-4.7-opus-abliterated-q4_k_m.gguf` | `.83` | `19.71` | `78.96 tok/s` | `22.81 tok/s` |
| 37 | `minicpm-v-4.7-35b-a3b` | `MiniCPM-V-4_7-35B-A3B-Q4_K_M.gguf` | `.83` | `19.71` | `79.71 tok/s` | `23.14 tok/s` |
| 45 | `nemotron-3.5-bolt-74b-a9b` | `NVIDIA-Nemotron-3.5-Bolt-74B-A9B-UD-Q4_K_XL` | `.83` | `46.77` | `29.18 tok/s` | `13.46 tok/s` |
| 47 | `qwen3-coder-next-80b` | `Qwen3-Coder-Next-Q5_K_M` | `.83` | `52.94` | `22.95 tok/s` | `8.03 tok/s` |
| 48 | `gpt-oss-120b-heretic-v2` | `kldzj_gpt-oss-120b-heretic-v2-MXFP4_MOE` | `.72` | `59.03` | `23.14 tok/s` | `8.24 tok/s` |
| 49 | `qwen3.5-122b-a10b-abliterated` | `Qwen3.5-122B-A10B-abliterated-v1.i1-IQ4_XS.gguf` | `.83` | `60.76` | `22.08 tok/s` | `7.70 tok/s` |
| 51 | `nemotron-3.5-super-vl-120b` | `NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-UD-Q4_K_XL` | `.83` | `82.55` | `19.03 tok/s` | `8.40 tok/s` |
| 52 | `rvn-qwen3.8-flash-next-abliterated-177b` | `RVN-Qwen3.8-Flash-Next-IQ3_M` | `.83` | `83.39` | `22.87 tok/s` | `7.03 tok/s` |
| 53 | `ling-3.0-flash-abliterated-128b` | `Ling-3.0-flash-abliterated-APEX-Balanced.gguf` | `.83` | `85.96` | `10.16 tok/s` | `6.21 tok/s` |
| 54 | `hy3-295b-heretic` | `Hy3-heretic.i1-IQ2_M.gguf` | `.72` | `89.42` | `8.80 tok/s` | `3.78 tok/s` |
| 55 | `glm-5.3-flash-uncensored` | `GLM-5.3-Flash-Uncensored-IQ2_XXS-00001-of-00003.gguf` | `.72` | `90.44` | `8.05 tok/s` | `1.88 tok/s` |
| 56 | `command-a-plus-111b` | `command-a-plus-05-2026-Q4_K_M-00001-of-00004.gguf` | `.72` | `125.81` | `1.31 tok/s` | `2.40 tok/s` |
| 57 | `minimax-m2.7-ultra-uncensored-heretic` | `MiniMax-M2.7-BF16-ultra-uncensored-heretic-Q4_K_M.gguf` | `.72` | `128.84` | `2.80 tok/s` | `4.39 tok/s` |
| 58 | `glm-5.3-flash-abliterated` | `GLM-5.3-Flash-UD-IQ4_XS-00001-of-00005.gguf` | `.83` | `147.14` | `1.35 tok/s` | `0.73 tok/s` |
| 59 | `mimo-v2.6-flash-rl-heretic-311b` | `MiMo-V2.6-Flash-RL-Uncensored-Heretic-MXFP4-00001-of-00002.gguf` | `.83` | `155.87` | `1.39 tok/s` | `4.20 tok/s` |
| 60 | `beam-1.0-501b-a23b` | `Beam-1.0-501B-A23B-UD-Q2_K_XL-00001-of-00005.gguf` | `.72+.228` | `174.04` | `1.16 tok/s` | `3.05 tok/s` |
| 61 | `nemotron-3-ultra-550b-a55b` | `NVIDIA-Nemotron-3-Ultra-550B-A55B-UD-Q2_K_XL-00001-of-00006.gguf` | `.72+.228` | `188.30` | `1.75 tok/s` | `1.37 tok/s` |
| 62 | `minimax-m3-426b-uncensored` | `MiniMax-M3-uncensored-IQ4_XS-00001-of-00005.gguf` | `.72+.228` | `189.13` | `0.55 tok/s` | `1.59 tok/s` |
| 63 | `ling-3.1-flash-564b` | `Ling-3.1-flash-AD-IQ2_M-00001-of-00005.gguf` | `.83` | `203.10` | `2.61 tok/s` | `1.34 tok/s` |
| 64 | `muse-spark-816b-a42b` | `Muse-Spark-Open-816B-A42B-UD-IQ2_XXS-00001-of-00006.gguf` | `.83+.125` | `210.08` | `0.41 tok/s` | `0.13 tok/s` |
| 65 | `deepseek-v3.2-685b` | `DeepSeek-V3.2-UD-Q2_K_XL-00001-of-00006.gguf` | `.72+.228` | `229.67` | `1.73 tok/s` | `2.47 tok/s` |
| 66 | `glm-5.3-753b` | `GLM-5.3-UD-Q2_K_XL-00001-of-00007.gguf` | `.83+.125` | `236.44` | `1.95 tok/s` | `1.71 tok/s` |
| 67 | `mimo-v2.6-pro-1024b` | `MiMo-V2.6-Pro-MOPD-BPW2.0-00001-of-00007.gguf` | `.83+.125` | `238.22` | `2.92 tok/s` | `2.42 tok/s` |

- **Non-GGUF Flagship Validation (`Uniboshi--Kimi-K3-Abliterated-V1`)**: `.83` (`1,453.79 GiB`, `113` files, `96` `Safetensors` shards, `497,220` tensors, header scan `37,993.37 ms`).
- **Always-Warm Production Champion on `.83:18080` (`& :8080/:8082`)**: Following completion of `mimo-v2.6-pro-1024b` (`#85/87`), `.83` is hot-pinned with `Qwen3.6-35B-A3B-Heretic` (`Q4_K_M`, `/mnt/ai-models/qwen3.6-35b-a3b-heretic/Qwen3.6-35B-A3B-Heretic-Q4_K_M.gguf`, `-ngl 99 -ot ".ffn_.*_exps.=CPU" -fa on -ctk q8_0 -ctv q8_0 -c 16384 --jinja -t 48`), delivering `0.159s` warm TTFT (`0.985s` cold TTFT) and `18.68 tok/s` (1xT4+AVX512) / `65.80 tok/s` (2xT4) with `enable_thinking: false`.

---

## 4. Multimodal, Vision, Audio & Diffusion Models in Vault

- **Image Generation**: `flux.1dev-abliteratedv2` (`.83`, `33.31 GiB`, 28 Diffusers `Safetensors` files, 8 shards, 1,819 tensors) + Local Flux/HUD/Diagram generator on `:4079/v1`.
- **Vision & Captcha OCR**: `qwen2.5vl:7b` (`.72`), `MiniCPM-V-4_7-35B-A3B` (`.83`), `NVIDIA-Nemotron-3.5-Super-VL-120B` (`.83`), `CaptchaKraken-v1.2` (`.72`), `captcha-agent` (`.72`, `35.09 GiB`), `pix2struct-docvqa-large` (`.83`), `git-large-textvqa` (`.83`), `ocr-captcha-v3` (`.72`).
- **Speech, ASR & Audio**: `ultravox-v0_5-llama-3_2-1b` (`.83`), `moss-transcribe-diarize` (`.83`), `vibevoice-asr-hf` (`.83`, `15.53 GiB`), `qwen2-audio-7b-instruct` (`.83`, `15.65 GiB`), `audio-flamingo-3-hf` (`.83`, `16.73 GiB`), `moss-music-8b-instruct-gguf` (`.83`, `8.11 GiB`), plus local Whisper STT & Neural TTS on `:4079/v1`.

---

## 5. `bd-airgap` WAN Isolation & `bd-raw-ai` CLI

- **`/home/mboyle/bin/bd-airgap`**:
  - `bd-airgap on`: Blocks outbound WAN traffic to external cloud LLM APIs (`api.openai.com`, `api.anthropic.com`, `generativelanguage.googleapis.com`) via `iptables` while keeping `10.0.0.0/8` and `127.0.0.0/8` LAN traffic 100% open.
  - `bd-airgap off`: Restores hybrid Local + Cloud mode.
  - `bd-airgap status`: Reports live firewall rules and local endpoint reachability.
- **`/home/mboyle/bin/bd-raw-ai`**:
  - Zero-guardrail CLI connecting directly to local `llama-server` / LiteLLM without system prompt injection or moderation filters.
