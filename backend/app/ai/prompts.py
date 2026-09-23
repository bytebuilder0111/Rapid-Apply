"""The JD-analysis prompt, versioned. Store PROMPT_VERSION on every analysis row so we
can tell which prompt produced a given result after this file changes."""

PROMPT_VERSION = "jd-analysis-v1"

SYSTEM_PROMPT = """You are a technical recruiter's assistant. Given a job description and a
list of candidate resume profiles, identify the JD's main backend skill/framework, secondary
skills, seniority level, and key requirements. Then recommend the single best-matching profile
from the list by id, with a confidence score and a short reason (at most 3 sentences).

If no profile is a reasonable match, set recommended_profile_id to null and explain why in
reasoning. Only ever return a recommended_profile_id that is one of the ids given to you."""


def build_user_prompt(job_description: str, profiles: list[dict]) -> str:
    profile_lines = "\n".join(
        f"- id={p['id']} name={p['name']!r} tech_stacks={p['tech_stacks']}" for p in profiles
    )
    profile_section = profile_lines or "(no active profiles for this client)"
    return f"Candidate profiles:\n{profile_section}\n\nJob description:\n{job_description.strip()}"
