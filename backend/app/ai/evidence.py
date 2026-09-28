"""Turns the model's per-resume checks into the final match, using evidence from the texts.

The model assesses every resume but never picks the winner; its per-resume checks proved
unreliable (e.g. claiming a Java resume "matches Python"). A resume can win only if, measured
from the JD text and the resume's own summary/skills:
- it has at least one of the languages the JD names (a shared framework like React isn't
  enough when the JD also names Python),
- the model judged it the same kind of role, unless it covers 75%+ of the stack anyway.
Among those, the resume with the most of the named stack wins (languages count double); JDs
often list alternatives ("Swift, Kotlin or Java"), so no minimum share is required.
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
# Share of the JD's named stack (languages count double) above which the model's "different
# role" judgment is overruled: the model's per-resume checks are too unreliable to veto a
# resume that has nearly everything the JD names.
STRONG_COVERAGE = 0.75
# Tokens that make a stack term a programming language (".NET" counts, via C#/.NET resumes).
_LANGUAGE_TOKENS = {
    "python", "java", "go", "c#", "c++", "php", "ruby", "javascript", "typescript", "node",
    "kotlin", "swift", "objective", "scala", "rust", "elixir", "clojure", "dart", "perl",
    "haskell", "erlang", "net", "zig",
}  # fmt: skip
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
    and "Java" doesn't match "JavaScript" because tokens are compared whole. Version numbers
    are ignored."""
    term_tokens = _tokens(term)
    # Version numbers don't have to match: "Java 17" is named by a resume that says "Java".
    words = {t for t in term_tokens if not t.isdigit()} or term_tokens
    return bool(words) and words <= text_tokens


def _is_generic(term: str) -> bool:
    return _tokens(term) <= _GENERIC_TOKENS


# A resume that names a framework also has its language, even if it never says so
# ("Django REST Framework APIs" is Python work).
_IMPLIED_LANGUAGE = {
    "django": "python", "flask": "python", "fastapi": "python", "spring": "java",
    "rails": "ruby", "laravel": "php", "symfony": "php", "asp": "c#", "nestjs": "node",
    "express": "node", "swiftui": "swift", "ktor": "kotlin", "phoenix": "elixir",
}  # fmt: skip


def _resume_tokens(resume: dict) -> set[str]:
    tokens = _tokens(" ".join(resume["skills"]) + " " + resume["summary"])
    return tokens | {_IMPLIED_LANGUAGE[t] for t in tokens if t in _IMPLIED_LANGUAGE}


def _is_language(term: str) -> bool:
    return bool(_tokens(term) & _LANGUAGE_TOKENS)


def _weight(term: str) -> int:
    return 2 if _is_language(term) else 1


def _clean(value: str | None) -> str | None:
    if value is None or value.strip().lower() in _EMPTY_VALUES:
        return None
    return value.strip()


# Languages the code can spot in a JD on its own, when the model's extraction comes back
# empty. Only unambiguous words: "Go" and ".NET" also occur in ordinary English text.
_DETECTABLE_LANGUAGES = {
    "python": "Python", "java": "Java", "javascript": "JavaScript", "typescript": "TypeScript",
    "kotlin": "Kotlin", "swift": "Swift", "php": "PHP", "ruby": "Ruby", "rust": "Rust",
    "scala": "Scala", "elixir": "Elixir", "c#": "C#", "c++": "C++", "golang": "Go",
}  # fmt: skip


def verified_core_stack(claimed: list[str], job_description: str) -> list[str]:
    """The claimed core technologies that really appear in the JD and aren't generic tools.
    If the model named none, falls back to languages the JD text itself names."""
    jd_tokens = _tokens(job_description)
    verified: list[str] = []
    for term in (t.strip() for t in claimed):
        seen = term.lower() in {v.lower() for v in verified}
        if _named_in(term, jd_tokens) and not _is_generic(term) and not seen:
            verified.append(term)
    if not verified:
        raw = set(re.findall(r"[a-z0-9+#]+", job_description.lower()))
        verified = [name for word, name in _DETECTABLE_LANGUAGES.items() if word in raw]
    return verified


def _names(resumes: list[dict]) -> str:
    return ", ".join(r["name"] for r in resumes)


def skip_reason(response: AnalysisResponse) -> str | None:
    """The client only takes senior-enough, US-remote jobs. A reason to skip the job, or None.
    A JD that doesn't state its location isn't skipped (the UI flags it instead)."""
    where = response.location_note.strip()
    detail = f" ({where})" if where and where.lower() != "not stated" else ""
    if response.seniority == "intern":
        return "Internship role."
    if response.seniority == "junior":
        return "Junior / entry-level role."
    # Office-based first: the model tends to also flag "must be in Austin" as relocation.
    if response.work_arrangement == "hybrid":
        return f"Hybrid role, not fully remote{detail}."
    if response.work_arrangement == "onsite":
        return f"On-site role, not remote{detail}."
    if response.work_arrangement == "remote" and response.remote_location == "non_us":
        return f"Remote only outside the US{detail}."
    if response.relocation_required:
        return f"Requires relocation{detail}."
    return None


def decide_match(
    response: AnalysisResponse, job_description: str, resumes: list[dict]
) -> AnalysisResult:
    jd_tokens = _tokens(job_description)
    core = verified_core_stack(response.jd_core_stack, job_description)

    framework = _clean(response.backend_framework)
    if framework and not _named_in(framework, jd_tokens):
        framework = None
    main_skill = _clean(response.main_backend_skill)
    if not main_skill or not _named_in(main_skill, jd_tokens) or _is_generic(main_skill):
        main_skill = ", ".join(core[:2]) or "Not specified"

    checks = {c.resume_id: c for c in response.resume_checks}
    languages = [t for t in core if _is_language(t)]
    total = sum(_weight(t) for t in core)

    # Everything below is measured from the resume text itself; the model's per-resume check
    # only breaks ties and vetoes a different kind of role when coverage is partial.
    scored = []  # (resume, overlap, coverage, has_language)
    for p in resumes:
        resume_tokens = _resume_tokens(p)
        overlap = [t for t in core if _named_in(t, resume_tokens)]
        if overlap:
            coverage = sum(_weight(t) for t in overlap) / total
            has_language = not languages or any(t in overlap for t in languages)
            scored.append((p, overlap, coverage, has_language))
    with_language = [s for s in scored if s[3]]

    def fit(p: dict) -> float:
        return checks[p["id"]].fit if p["id"] in checks else 0.0

    def role_ok(p: dict, coverage: float) -> bool:
        same = p["id"] in checks and checks[p["id"]].same_role
        return same or coverage >= STRONG_COVERAGE

    candidates = [s for s in with_language if role_ok(s[0], s[2])]

    def best_of(options):
        return max(options, key=lambda s: (s[2], fit(s[0])))

    recommended, confidence = None, 0.0
    skip = skip_reason(response)
    stack = ", ".join(core)
    if skip:
        reasoning = f"Skipped: {skip}"
    elif not core:
        reasoning = (
            "This JD doesn't name a specific programming language or framework, so none of "
            "your resumes can be confirmed as a match."
        )
    elif not scored:
        reasoning = f"None of your resumes include the stack this JD names ({stack})."
    elif not with_language:
        best, overlap, _, _ = best_of(scored)
        reasoning = (
            f"No resume has the language this JD needs ({', '.join(languages)}). The closest, "
            f"{best['name']}, only shares {', '.join(overlap)}."
        )
    elif not candidates:
        names = _names([s[0] for s in with_language])
        verb = "has" if len(with_language) == 1 else "have"
        reasoning = (
            f"{names} {verb} part of the named stack ({stack}), "
            f"but for a different kind of role than this {response.role_type} job."
        )
    else:
        best, overlap, coverage, _ = best_of(candidates)
        recommended = best["id"]
        confidence = round(0.7 * coverage + 0.3 * fit(best), 2)
        missing = [t for t in core if t not in overlap]
        reasoning = f"{best['name']} has {', '.join(overlap)} from the stack this JD names" + (
            f"; missing {', '.join(missing)}." if missing else " (all of it)."
        )

    return AnalysisResult(
        jd_summary=response.jd_summary,
        role_type=response.role_type,
        work_arrangement=response.work_arrangement,
        remote_location=response.remote_location,
        relocation_required=response.relocation_required,
        location_note=response.location_note,
        skip_reason=skip,
        jd_core_stack=core,
        main_backend_skill=main_skill,
        backend_framework=framework,
        secondary_skills=response.secondary_skills,
        seniority=response.seniority,
        key_requirements=response.key_requirements,
        recommended_resume_type_id=recommended,
        confidence=confidence,
        reasoning=reasoning,
    )
