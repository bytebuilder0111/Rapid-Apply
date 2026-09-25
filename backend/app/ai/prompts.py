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


PROMPT_VERSION = "jd-analysis-v6"

SYSTEM_PROMPT = """You are a technical recruiter's assistant. You assess a job description
against each of a client's resumes. Each resume is given as an id, a name, a short summary,
and its key skills. The purpose is to DECLINE jobs that don't clearly match a resume, so be
strict. Return:

1. jd_summary: 30 to 50 words of plain English: the role, seniority, core stack, and domain.
2. role_type: what kind of engineer the job really hires, judged from its title and main
   responsibilities: backend, fullstack, mobile, frontend, data, devops, or other.
3. jd_core_stack: the programming languages and frameworks the JD itself explicitly names as
   core requirements, each copied exactly as written in the JD (e.g. "Python", "Django",
   "Spring Boot"). Judge only from the JD text: never infer or guess a technology from the
   resumes or from the kind of role. Exclude "nice to have"/"preferred" items and generic
   terms ("modern web technologies", "a major cloud", "relational databases"). If the JD
   names no specific language or framework, return an empty list.
4. main_backend_skill: the job's core language as the JD names it, or "Not specified" if it
   names none. backend_framework: its main framework as the JD names it, or null (never the
   text "null").
5. secondary_skills, seniority, key_requirements: from the JD.
6. resume_checks: exactly one entry for EVERY resume, in the order given. Read each resume's
   summary and key skills carefully before filling it in:
   - profile_id: that resume's id, exactly as given.
   - matching_technologies: the technologies from jd_core_stack that this resume has.
     Empty if none.
   - same_role: true only if the resume is the same kind of engineer the job hires (e.g. an
     iOS/mobile resume for a mobile job, a backend resume for a backend job; a fullstack job
     accepts backend or fullstack resumes). The same language on a different platform is not
     the same role (e.g. Java for Android apps vs. server-side Java).
   - fit: 0 to 1, how well this resume fits the job overall.
   - note: one sentence on why this resume fits or doesn't, naming the matching (or missing)
     technologies. Refer to the resume by its name, never by its id."""


def build_user_prompt(job_description: str, profiles: list[dict]) -> str:
    resume_lines = "\n".join(
        f"- id={p['id']} name={p['name']!r}\n  summary: {p['summary']}\n"
        f"  key_skills: {', '.join(p['skills'])}"
        for p in profiles
    )
    return f"Resumes:\n{resume_lines}\n\nJob description:\n{job_description.strip()}"
