# 🔴🟡🟢 LLM / AI Safety Check

*Red light, green light for self-hosted AI — would you run this on your laptop?*

## Leaderboard

| Verdict | Tool | Category | Significance | What happened next |
|---|---|---|---|---|
| 🟡 YELLOW | autogpt | AGENT | autonomous LLM agent that executes its own plans | AutoGPT had a DoS vulnerability disclosed in 2025. |
| 🔴 RED | mlflow | INFERENCE_SERVER | ML lifecycle platform commonly self-hosted | MLflow disclosed multiple critical vulnerabilities in early 2026. |
| 🔴 RED | anthropic | GATEWAY | vendor-name package; squat-check showcase | Anthropic patched Claude Code RCE bug after discovery. |
| 🔴 RED | langchain | ORCHESTRATION | dominant LLM orchestration framework | LangChain suffered multiple critical vulnerabilities disclosed 2024‑2026. |
| 🟡 YELLOW | ollama | INFERENCE_SERVER | local LLM runner | Ollama v0.5.11 DoS vulnerability via malicious model download |
| 🟡 YELLOW | gradio | INFERENCE_SERVER | ML demo UI server (hosts public shares) | Gradio CVE-2024-10569 updated with SSVC details 2025-2026. |
| 🟡 YELLOW | chromadb | VECTOR_DB | popular embedded vector database | Critical unpatched RCE vulnerability affects ChromaDB v1.0.0-1.5.8 |
| 🟡 YELLOW | litellm | GATEWAY | multi-provider LLM gateway/proxy | CVE-2024-9606 for litellm updated mid-2026 with SSVC details. |
| 🔴 RED | llama-index | ORCHESTRATION | RAG framework connecting LLMs to data | Critical SQLi vulnerability discovered and patched in LlamaIndex. |
| 🟡 YELLOW | chatgpt | GATEWAY | A lightweight Python library that simplifies calling the OpenAI ChatGPT API. | ChatGPT disclosed privilege/authorization vulnerability after mid-2023. |
| 🟡 YELLOW | visual-chatgpt | INFERENCE_SERVER | Visual ChatGPT combines visual foundation models with ChatGPT to enable multimodal reasoning via a Gradio demo server. | Post‑mid‑2023, Visual ChatGPT revealed privilege/authorization flaw (CVE‑2025‑2320). |
| 🟡 YELLOW | stablediffusion | INFERENCE_SERVER | Stable Diffusion repo offers code to run the text‑to‑image model, often serving via a web UI for image generation. | Vulnerability found allowing privilege escalation via insecure permissions. |
| 🟡 YELLOW | agentgpt | AGENT | AgentGPT is a web‑based platform for creating and running autonomous AI agents that can use tools and execute code. | Source gives no details on AgentGPT after mid‑2023. |
| 🟡 YELLOW | gpt-sovits | INFERENCE_SERVER | GPT‑SoVITS combines GPT and SoVITS for high‑quality voice cloning, exposing an inference server for TTS synthesis. | Source lacks post-mid-2023 event details |
| 🟡 YELLOW | swin-transformer | INFERENCE_SERVER | A hierarchical vision transformer that achieved state-of-the-art results on various computer vision tasks. | Source does not mention swin‑transformer after mid‑2023. |
| 🟡 YELLOW | shell_gpt | GATEWAY | A shell integration that lets users query LLMs directly from the terminal and execute suggested commands. | shell_gpt disclosed a privilege escalation flaw post-mid-2023. |
| 🟡 YELLOW | llm | GATEWAY | A command-line utility that provides a unified interface to run prompts against multiple local and remote LLMs. | SSVC added: exploitation PoC, automatable, total impact. |

## Case Studies

### 🔴 mlflow
*ML lifecycle platform commonly self-hosted*
- **cve:** 5 CRITICAL / 2 HIGH / 0 MODERATE advisories; worst CVSS 10.0
- **capability:** capabilities: exposes_server, loads_pickled_models
- **staleness:** last release 13 days ago
- **blast:** 0 downstream dependents
- **health:** 15665 stars / 1229 open issues
- **identity:** identity looks legitimate
- **What actually happened:** MLflow disclosed multiple critical vulnerabilities in early 2026. ([source](https://app.opencve.io/cve?page=2&product=mlflow&vendor=lfprojects))

### 🟡 autogpt
*autonomous LLM agent that executes its own plans*
- **cve:** 0 CRITICAL / 0 HIGH / 0 MODERATE advisories
- **capability:** capabilities: executes_code, accesses_network
- **staleness:** no release date available
- **blast:** 0 downstream dependents
- **health:** 164209 stars / 114 open issues
- **identity:** identity looks legitimate
- **What actually happened:** AutoGPT had a DoS vulnerability disclosed in 2025. ([source](https://www.sentinelone.com/vulnerability-database/cve-2025-32423))

### 🔴 anthropic
*vendor-name package; squat-check showcase*
- **cve:** 0 CRITICAL / 0 HIGH / 0 MODERATE advisories
- **capability:** capabilities: accesses_network
- **staleness:** last release 2200 days ago (>2y)
- **blast:** 1 downstream dependents
- **health:** 24 stars / 0 open issues
- **identity:** suspected squat / name-confusion package
- **What actually happened:** Anthropic patched Claude Code RCE bug after discovery. ([source](https://www.sentinelone.com/vulnerability-database/cve-2025-59536))

## Common Dangers

- **Unrestricted code execution with network access** — seen in autogpt, langchain, llama-index. *Unscrew:* Run code in a sandboxed environment and disable outbound network unless explicitly required.
- **Exposure of server endpoints without authentication** — seen in mlflow, ollama, gradio, chromadb. *Unscrew:* Enforce authentication, use API gateways, and restrict server binding to trusted interfaces.
- **Deserialization of untrusted pickle data leading to arbitrary code execution** — seen in mlflow. *Unscrew:* Replace pickle with safe serialization formats (e.g., JSON) and validate all incoming data before deserialization.
- **Handling of credentials combined with network communication** — seen in litellm. *Unscrew:* Store credentials in a secret manager, use short-lived tokens, and ensure all network traffic is encrypted.