
# 🔴🟡🟢 LLM / AI Safety Check

<img width="899" height="580" alt="CleanShot 2026-07-11 at 18 16 46@2x" src="https://github.com/user-attachments/assets/51f9dc66-f59e-41ca-ab0b-3ff0c4b1c6fe" />

**Red light, green light for self-hosted AI. Every AI tool gets a nutrition label.**
Built for the Nebius × Emergence hackathon — Scenario 5: Software Supply Chain.

---

We're all installing AI tools as fast as they ship — agents, MCPs, whatever hit the front page this week — with zero idea if they're safe to run. **LLM / AI Safety Check** gates them: six data-backed signals per tool, worst-signal-wins, a 🔴 RED / 🟡 YELLOW / 🟢 GREEN verdict — with the evidence, the SQL query that produced it, and the fix.
CHECK IT OUT LIVE HERE: https://ai-safety-check-79hkfz9cpbhk9m82wpzpgr.streamlit.app/
** Ask what the latest greatest AI/LLM tools are... get an evidence backed security audit!

## The hook: hindsight as a feature

The dataset is a deps.dev / OSV snapshot collected by CRAFT frozen at ~June 2023. That's not a limitation — it's the experimental design:

1. Verdicts use **only what was knowable in mid-2023**
2. A live web lookup then reveals **what actually happened after** the snapshot
3. The result is a **hindsight validation study**: proof the gating predicts real-world blowups

**The data was screaming in June 2023. Nobody was listening. This makes sure somebody is.**

## What it found

| Tool                      | Verdict | Why                                                                                                                                         | What happened next                                                     |
| ------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| **mlflow**                | 🔴 RED  | 13 advisories in-snapshot, **two CVSS 10.0s** (unauthenticated arbitrary file read via `mlflow server`/`ui`)                                | Mass-exploited in the wild post-2023. **The gate called it.**          |
| **AutoGPT**               | 🔴 RED  | **Clean CVE sheet** — but it executes model-generated code on your machine *by design*. The attack surface is "everything the agent reads." | The capability signal catches what CVE-counting alone would pass.      |
| **`anthropic` npm squat** | 🔴 RED  | One version, no repo, **zero CVEs** — and that's the horror. CVEs only exist for software someone audited.                                  | **Zero CVEs ≠ safe.** Squatted names carry the cleanest sheets of all. |

Plus a **Common Dangers** panel: findings clustered into anti-patterns (web UIs bundled into server processes, agents that execute generated code, zero-CVE squats, "recommended but abandoned") with remediation for each.

## PROPS TO CLAUDE/ANTHROPIC FOR KILLING MY ACCESS MID HACKATHON.
<img width="1902" height="334" alt="CleanShot 2026-07-11 at 12 51 06@2x" src="https://github.com/user-attachments/assets/83afcafe-1fc7-4a07-8b0d-4e473596b91a" />
