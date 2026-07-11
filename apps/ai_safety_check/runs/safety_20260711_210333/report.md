# 🔴🟡🟢 LLM / AI Safety Check

*Red light, green light for self-hosted AI — would you run this on your laptop?*

## Leaderboard

| Verdict | Tool | Category | Significance | What happened next |
|---|---|---|---|---|
| 🟡 YELLOW | autogpt | AGENT | autonomous LLM agent that executes its own plans | AutoGPT had a DoS vulnerability disclosed in 2025. |
| 🔴 RED | mlflow | INFERENCE_SERVER | ML lifecycle platform commonly self-hosted | MLflow disclosed multiple critical vulnerabilities in early 2026. |
| 🔴 RED | anthropic | GATEWAY | vendor-name package; squat-check showcase | Anthropic patched Claude Code RCE bug after discovery. |

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

- **executes_code** — seen in autogpt. *Unscrew:* Run any code execution in a tightly sandboxed environment with limited privileges.
- **accesses_network** — seen in autogpt, anthropic. *Unscrew:* Enforce outbound network controls and restrict connections to approved destinations only.
- **exposes_server** — seen in mlflow. *Unscrew:* Disable unnecessary service exposure and bind listeners to internal interfaces or localhost.
- **loads_pickled_models** — seen in mlflow. *Unscrew:* Avoid deserializing untrusted pickle data; use safe serialization formats instead.