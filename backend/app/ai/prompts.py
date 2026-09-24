"""All prompts, versioned. PROMPT_VERSION is stored on every analysis row so we can tell
which prompt produced a given result after this file changes."""

RESUME_PROMPT_VERSION = "resume-summary-v1"

RESUME_SYSTEM_PROMPT = """You summarize a candidate's resume so it can later be matched
against job descriptions. Return:

- summary: 30 to 50 words of plain, easy-to-read English. Start with the candidate's role
  and years of experience, then their core language(s) and framework(s), then their main
  domains or kinds of systems built. No names, contact details, or company names.
- key_skills: the candidate's most prominent technical skills, most important first,
  at most 8, each a short name (e.g. "Python", "Django", "PostgreSQL", "AWS")."""


def build_resume_prompt(resume_text: str) -> str:
    return f"Resume:\n{resume_text.strip()}"


PROMPT_VERSION = "jd-analysis-v4"

SYSTEM_PROMPT = """You are a technical recruiter's assistant. You match a job description
against a client's resumes. Each resume is given as an id, a name, a short summary, and its
key skills. Return:

1. jd_summary: 30 to 50 words of plain English: the role, seniority, core stack, and domain.
2. role_type: what kind of engineer the job really hires, judged from its title and main
   responsibilities: backend, fullstack, mobile, frontend, data, devops, or other.
3. main_backend_skill: the job's core language as the JD names it (never empty; for a
   mobile role e.g. "Swift, Kotlin"). backend_framework: its main framework, or null.
4. secondary_skills, seniority, key_requirements: from the JD.
5. recommended_profile_id: the id of the resume that best fits this job. A resume fits only
   if its role and core language/stack match what the job mainly needs. Don't match on
   incidental overlap: "nice to have" technologies, or the same language used on a
   different platform (e.g. Java for Android apps vs. server-side Java). If no resume is a
   genuine fit, set it to null.
6. confidence (0 to 1) that the recommended resume fits, and reasoning in at most 3
   sentences: why that resume fits best, or why none of them does. Refer to resumes by
   their name, never by id.

Only ever return a recommended_profile_id that is one of the ids given to you."""


def build_user_prompt(job_description: str, profiles: list[dict]) -> str:
    resume_lines = "\n".join(
        f"- id={p['id']} name={p['name']!r}\n  summary: {p['summary']}\n"
        f"  key_skills: {', '.join(p['skills'])}"
        for p in profiles
    )
    return f"Resumes:\n{resume_lines}\n\nJob description:\n{job_description.strip()}"
