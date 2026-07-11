"""Natural-language questions handed to CRAFT generate_sql. Kept in one place
so the audit trail and prompt-tuning live together."""


def discover_top_ai_projects(limit: int = 30) -> str:
    return (
        f"What are the top {limit} most-starred projects whose name relates to LLMs, AI agents, "
        "machine learning, or generative AI (names containing gpt, llm, llama, agent, langchain, "
        "transformer, diffusion, stable, bert, or the words ai/ml)? Show ProjectName, ProjectType, "
        "StarsCount, ForksCount, and OpenIssuesCount, ordered by StarsCount descending."
    )


def package_exists(names: list[str], system: str) -> str:
    joined = ", ".join(f"'{n}'" for n in names)
    return (f"For {system} packages whose name is one of {joined}, show the package name, the number "
            "of distinct versions, and the most recent UpstreamPublishedAt date.")


def advisories_for(name: str) -> str:
    return (f"Find all security advisories affecting the package '{name}'. The link is the Advisories "
            "column in PACKAGEVERSIONS joined to ADVISORIES on SourceID. Show advisory Title, "
            "CVSS3Score, and GitHubSeverity, ordered by CVSS3Score descending.")


def staleness_for(name: str, system: str) -> str:
    return (f"For the {system} package '{name}', show the most recent UpstreamPublishedAt date and the "
            "total number of versions.")


def dependents_for(name: str, system: str) -> str:
    return (f"How many distinct packages transitively depend on the {system} package '{name}' according "
            "to the DEPENDENTS table?")


def health_for(name: str) -> str:
    return (f"For projects whose name contains '{name}', show StarsCount, ForksCount, OpenIssuesCount, "
            "and Licenses from the PROJECTS table, ordered by StarsCount descending, limit 5.")


def identity_check(name: str) -> str:
    return (f"Across all systems (PYPI, NPM, MAVEN, CARGO, GO, NUGET), show every System and version count "
            f"for packages named exactly '{name}' in PACKAGEVERSIONS.")
