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