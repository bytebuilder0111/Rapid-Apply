"""Turns the model's per-resume checks into the final match, using evidence from the texts.

The model assesses every resume but never picks the winner. A resume can win only if:
- it contains a core technology the JD explicitly names (checked here against both the JD
  text and the resume's summary/skills, so a technology the model invents can't count), and
- the model judged it the same kind of role as the job.
Otherwise the result is a "Dismatched JD" with a specific reason."""

import re

from app.ai.schemas import AnalysisResponse, AnalysisResult

# Spelling variants treated as the same token when comparing JD and resume text.
_ALIASES = {
    "golang": "go",
    "nodejs": "node",
    "postgres": "postgresql",
    "reactjs": "react",
    "vuejs": "vue",
    "dotnet": "net",
    "k8s": "kubernetes",
}
_EMPTY_VALUES = {"", "null", "none", "n/a", "na", "not specified", "unspecified"}
# A resume that shares the stack and role still has to be judged at least this good a fit.
MIN_FIT = 0.5
# Tools, platforms and datastores that nearly every resume lists. They never count as a
# JD's core stack, so a match can't rest on incidental overlap like "CI/CD" or "AWS".
_GENERIC_TOKENS = {
    "git", "github", "gitlab", "ci", "cd", "actions", "jenkins", "docker", "kubernetes",
    "terraform", "pulumi", "aws", "gcp", "azure", "cloud", "linux", "sql", "nosql",
    "postgresql", "mysql", "mongodb", "redis", "kafka", "rest", "restful", "graphql", "api",
    "apis", "microservices", "html", "css", "agile", "scrum", "oauth", "sso",
}  # fmt: skip


def _tokens(text: str) -> set[str]:
    # Keep + and # so C++ and C# stay distinct from C; "Node.js" -> {"node", "js"}.
    raw = re.findall(r"[a-z0-9+#]+", text.lower())
    return {_ALIASES.get(t, t) for t in raw}


def _named_in(term: str, text_tokens: set[str]) -> bool:
    """True if every token of `term` appears in the text: "Spring Boot" needs both words,
    and "Java" doesn't match "JavaScript" because tokens are compared whole."""
    term_tokens = _tokens(term)
    return bool(term_tokens) and term_tokens <= text_tokens


def _is_generic(term: str) -> bool:
    return _tokens(term) <= _GENERIC_TOKENS


def _clean(value: str | None) -> str | None:
    if value is None or value.strip().lower() in _EMPTY_VALUES:
        return None
    return value.strip()


def verified_core_stack(claimed: list[str], job_description: str) -> list[str]:
    """The claimed core technologies that really appear in the JD and aren't generic tools."""
    jd_tokens = _tokens(job_description)
    verified: list[str] = []
    for term in (t.strip() for t in claimed):
        seen = term.lower() in {v.lower() for v in verified}
        if _named_in(term, jd_tokens) and not _is_generic(term) and not seen:
            verified.append(term)
    return verified


def _names(profiles: list[dict]) -> str:
    return ", ".join(p["name"] for p in profiles)


def decide_match(
    response: AnalysisResponse, job_description: str, profiles: list[dict]
) -> AnalysisResult:
    jd_tokens = _tokens(job_description)
    core = verified_core_stack(response.jd_core_stack, job_description)

    framework = _clean(response.backend_framework)
    if framework and not _named_in(framework, jd_tokens):
        framework = None
    main_skill = _clean(response.main_backend_skill)
    if not main_skill or not _named_in(main_skill, jd_tokens) or _is_generic(main_skill):
        main_skill = ", ".join(core[:2]) or "Not specified"

    checks = {c.profile_id: c for c in response.resume_checks}
    # Profiles that really contain a named core technology, with what they match on.
    with_stack = []
    for p in profiles:
        resume_tokens = _tokens(" ".join(p["skills"]) + " " + p["summary"])
        overlap = [t for t in core if _named_in(t, resume_tokens)]
        if overlap:
            with_stack.append((p, overlap))
    same_role = [
        (p, overlap, checks[p["id"]])
        for p, overlap in with_stack
        if p["id"] in checks and checks[p["id"]].same_role
    ]
    candidates = [c for c in same_role if c[2].fit >= MIN_FIT]

    def best_of(options):
        return max(options, key=lambda c: (c[2].fit, len(c[1])))

    recommended, confidence = None, 0.0
    if not core:
        reasoning = (
            "This JD doesn't name a specific programming language or framework, so none of "
            "your resumes can be confirmed as a match."
        )
    elif not with_stack:
        reasoning = f"None of your resumes include the stack this JD names ({', '.join(core)})."
    elif not same_role:
        verb = "shares" if len(with_stack) == 1 else "share"
        reasoning = (
            f"{_names([p for p, _ in with_stack])} {verb} part of the named stack "
            f"({', '.join(core)}), but for a different kind of role than this "
            f"{response.role_type} job."
        )
    elif not candidates:
        closest, _, check = best_of(same_role)
        reasoning = (
            f"The closest resume, {closest['name']}, fits only {round(check.fit * 100)}%. "
            f"{check.note}"
        )
    else:
        best, overlap, check = best_of(candidates)
        recommended, confidence = best["id"], check.fit
        reasoning = f"{check.note} Matches on: {', '.join(overlap)}."

    return AnalysisResult(
        jd_summary=response.jd_summary,
        role_type=response.role_type,
        jd_core_stack=core,
        main_backend_skill=main_skill,
        backend_framework=framework,
        secondary_skills=response.secondary_skills,
        seniority=response.seniority,
        key_requirements=response.key_requirements,
        recommended_profile_id=recommended,
        confidence=confidence,
        reasoning=reasoning,
    )
