"""The JD-analysis prompt, versioned. Store PROMPT_VERSION on every analysis row so we
can tell which prompt produced a given result after this file changes."""

PROMPT_VERSION = "jd-analysis-v2"

SYSTEM_PROMPT = """You are a technical recruiter's assistant. Given a job description and a
list of candidate resume profiles, analyze the JD and recommend a profile.

1. main_tech_stack: choose the ONE entry from "Allowed tech stacks" that best represents the
   JD's core backend technology, copied exactly as written. Judge by what the role mainly
   builds with, not by passing mentions. If none of the allowed stacks is the JD's core
   backend technology, set it to null.
2. main_backend_skill / backend_framework: the core backend language and framework as the JD
   itself names them (these may differ from the allowed list).
3. secondary_skills, seniority, key_requirements: from the JD.
4. recommended_profile_id: the single best-matching profile by id. When main_tech_stack is
   set, the recommended profile must include main_tech_stack in its tech_stacks. If no profile
   is a reasonable match, set it to null.
5. confidence (0 to 1) and reasoning (at most 3 sentences) for the recommendation.

Only ever return a recommended_profile_id that is one of the ids given to you."""


def allowed_stacks_from(profiles: list[dict]) -> list[str]:
    seen: dict[str, None] = {}
    for p in profiles:
        for stack in p["tech_stacks"]:
            seen.setdefault(stack, None)
    return list(seen)


def build_user_prompt(job_description: str, profiles: list[dict]) -> str:
    stacks = allowed_stacks_from(profiles)
    stacks_section = "\n".join(f"- {s}" for s in stacks) or "(none: set main_tech_stack to null)"
    profile_lines = "\n".join(
        f"- id={p['id']} name={p['name']!r} tech_stacks={p['tech_stacks']}" for p in profiles
    )
    profile_section = profile_lines or "(no active profiles for this client)"
    return (
        f"Allowed tech stacks:\n{stacks_section}\n\n"
        f"Candidate profiles:\n{profile_section}\n\n"
        f"Job description:\n{job_description.strip()}"
    )
