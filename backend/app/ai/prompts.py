"""The JD-analysis prompt, versioned. Store PROMPT_VERSION on every analysis row so we
can tell which prompt produced a given result after this file changes."""

PROMPT_VERSION = "jd-analysis-v3"

SYSTEM_PROMPT = """You are a technical recruiter's assistant. The candidate profiles are
BACKEND engineering resumes. Given a job description and those profiles, analyze the JD and
recommend a profile.

1. role_type: first decide what kind of engineer the job is really hiring, from its title and
   main responsibilities: backend (server-side services/APIs), fullstack (substantial backend
   AND frontend), mobile (iOS/Android apps), frontend, data (data/ML engineering), devops
   (infrastructure/SRE/platform ops), or other.
2. main_tech_stack: choose the ONE entry from "Allowed tech stacks" that is the JD's core
   backend technology, copied exactly as written. Rules:
   - If role_type is not backend or fullstack, set it to null.
   - Only count a language/framework used for server-side work in this job. A language listed
     for mobile apps (e.g. Java or Kotlin for Android, Swift for iOS) or for frontend work is
     NOT a backend stack, even if the same word appears in the allowed list.
   - "Preferred", "nice to have", "familiarity with", or "a plus" technologies never define
     the core stack.
   - If none of the allowed stacks is the core backend technology, set it to null.
3. main_backend_skill / backend_framework: the job's core language and framework as the JD
   itself names them. main_backend_skill is never empty: for a non-backend role give that
   role's main language(s) instead, e.g. "Swift, Kotlin" for a mobile role.
4. secondary_skills, seniority, key_requirements: from the JD.
5. recommended_profile_id: when main_tech_stack is set, the single best-matching profile by id,
   which must include main_tech_stack in its tech_stacks. When main_tech_stack is null, set it
   to null.
6. confidence (0 to 1) and reasoning (at most 3 sentences). When main_tech_stack is null,
   explain in reasoning why the JD doesn't match.

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
