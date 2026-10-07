"""Turns the model's per-resume checks into the final match, using evidence from the texts.

The model assesses every resume but never picks the winner; its per-resume checks proved
unreliable (e.g. claiming a Java resume "matches Python"). A resume can win only if, measured
from the JD text and the resume's own summary/skills:
- its backend language is one the JD names: a resume is judged by its backend, so a
  Python resume that also lists TypeScript for React front ends doesn't fit a TypeScript/Node
  job, and a shared framework like React is never enough,
- the model judged it the same kind of role, unless it covers 75%+ of the stack anyway.
Among those, the resume with the most of the named stack wins (languages count double).
Languages a JD lists as options ("at least one language, such as Java, Python or C#") form one
requirement that any of them meets.
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
# The model's fit a resume needs when it's a different role and the JD names no language.
MIN_FALLBACK_FIT = 0.3
# Job types that are a different discipline from backend/full-stack engineering. Such a job
# only fits a resume that is itself of that discipline, as its name or summary says; the
# model's per-resume role verdict proved too unstable to decide this.
_DISCIPLINE_WORDS = {
    "data": re.compile(
        r"\b(data (engineer|scientist)|ml engineer|machine learning|analytics engineer|mlops)"
    ),
    "devops": re.compile(
        r"\b(devops|sre|site reliability|platform engineer|infrastructure engineer|cloud engineer)"
    ),
    "mobile": re.compile(r"\b(ios|android|mobile|react native|flutter)\b"),
    "frontend": re.compile(r"\b(front[- ]?end|ui) (engineer|developer)"),
    "ai": re.compile(
        r"\b((ai|ml|llm|genai|gen ai|applied ai|machine learning)[ /-]*"
        r"(engineer|developer|scientist)|mlops)"
    ),
}
# How the reasoning names those job types.
_DISCIPLINE_NAMES = {
    "data": "data", "devops": "DevOps", "mobile": "mobile", "frontend": "frontend",
    "ai": "AI/ML",
}  # fmt: skip
# An AI/ML Engineer title. The model often calls such a job "other", which would let any
# resume with its language (Python) through.
_AI_TITLE = re.compile(
    r"\b(ai|ml|llm|genai|gen ai|applied ai|machine learning)[ /-]*engineer\b", re.I
)
# Tokens that make a stack term a programming language (".NET" counts, via C#/.NET resumes).
_LANGUAGE_TOKENS = {
    "python", "java", "go", "c#", "c++", "php", "ruby", "javascript", "typescript", "node",
    "kotlin", "swift", "objective", "scala", "rust", "elixir", "clojure", "dart", "perl",
    "haskell", "erlang", "net", "zig", "c",
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
    # Node.js and TypeScript are JavaScript.
    "node": "javascript", "typescript": "javascript",
}  # fmt: skip


def _resume_tokens(resume: dict) -> set[str]:
    tokens = _tokens(" ".join(resume["skills"]) + " " + resume["summary"])
    return tokens | {_IMPLIED_LANGUAGE[t] for t in tokens if t in _IMPLIED_LANGUAGE}


def _is_language(term: str) -> bool:
    return bool(_tokens(term) & _LANGUAGE_TOKENS)


def _weight(term: str) -> int:
    return 2 if _is_language(term) else 1


# Language tokens grouped by backend: TypeScript, JavaScript and Node are one backend.
_JS_FAMILY = "node"
_FAMILY = {
    "typescript": _JS_FAMILY, "javascript": _JS_FAMILY, "node": _JS_FAMILY, "c#": "dotnet",
    "net": "dotnet", "objective": "swift",
}  # fmt: skip


def _families(tokens: set[str]) -> set[str]:
    return {_FAMILY.get(t, t) for t in tokens & _LANGUAGE_TOKENS}


def _backend(families: set[str]) -> set[str]:
    """TypeScript/JavaScript next to a server-side language is front-end work, so the backend
    is the other language; on its own it means a Node backend."""
    return (families - {_JS_FAMILY}) or families


def jd_backend(languages: list[str]) -> set[str]:
    return _backend(_families(set().union(*(_tokens(t) for t in languages))))


def resume_backend(resume: dict) -> set[str]:
    """What a resume is for. Resume types are named after their backend ("Python", "Node",
    "GoLang"), so the name decides; otherwise the languages in its skills and summary."""
    return _families(_tokens(resume["name"])) or _backend(_families(_resume_tokens(resume)))


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


# A job-alert sign-up field that job boards pre-fill with the visitor's own location
# ("Location (city, state or zip code)" then "Beijing, 11 CN"). Pasted with the JD, the model
# reads it as the job's location.
_VISITOR_LOCATION_FIELD = re.compile(
    r"^\s*location\s*\(\s*city,\s*state,?\s*(or|/)\s*zip(\s*code)?\s*\)\s*\*?\s*$",
    re.IGNORECASE,
)


def strip_page_furniture(job_description: str) -> str:
    """Drops pasted form fields that describe the visitor, not the job: the field's label and
    the value on the next non-empty line."""
    lines = job_description.splitlines()
    kept: list[str] = []
    skip_value = False
    for line in lines:
        if _VISITOR_LOCATION_FIELD.match(line):
            skip_value = True
            continue
        if skip_value and line.strip():
            skip_value = False
            continue
        kept.append(line)
    return "\n".join(kept)


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


# Wording that turns a list of languages into options rather than requirements.
_ALTERNATIVE_MARKERS = re.compile(r"\b(or|such as|one of|any of|either|e\.g|for example)\b")


def language_options(languages: list[str], job_description: str) -> list[list[str]]:
    """Groups of the JD's languages that it offers as alternatives: 2+ of them named in one
    sentence that says "or", "such as", "one of", etc. Sentences that share a language merge."""
    groups: list[set[str]] = []
    # Lines are separate bullets, unless a line ends mid-list ("Java, Python, C#,\nTypeScript").
    text = re.sub(r",[ \t]*\r?\n", ", ", job_description)
    for sentence in re.split(r"[\n;]|(?<=[.!?])\s", text):
        if not _ALTERNATIVE_MARKERS.search(sentence.lower()):
            continue
        tokens = _tokens(sentence)
        named = {lang for lang in languages if _named_in(lang, tokens)}
        if len(named) < 2:
            continue
        for group in [g for g in groups if g & named]:
            named |= group
            groups.remove(group)
        groups.append(named)
    return [[lang for lang in languages if lang in g] for g in groups]


def _unnamed_language_pick(
    resumes: list[dict], jd_tokens: set[str], response: AnalysisResponse
) -> tuple[dict, list[str]] | None:
    """For a JD that names no language: the resume with the most of the tools and platforms
    the JD names (Kubernetes, AWS, PostgreSQL...), among those the model judged the same kind
    of role if any; the model's fit breaks ties. (resume, shared tools) or None.
    A data/DevOps/mobile/frontend job only considers resumes of that kind. With no resume of
    the same role, one needs some fit and a tool in common (an aerospace Systems Engineer job
    fits no software resume)."""
    checks = {c.resume_id: c for c in response.resume_checks}
    if response.role_type in _DISCIPLINE_WORDS:
        resumes = [p for p in resumes if fits_discipline(p, response.role_type)]
    jd_tools = jd_tokens & _GENERIC_TOKENS

    def shared(p: dict) -> list[str]:
        return sorted(jd_tools & _resume_tokens(p))

    def fit(p: dict) -> float:
        return checks[p["id"]].fit if p["id"] in checks else 0.0

    same_role = [p for p in resumes if p["id"] in checks and checks[p["id"]].same_role]
    pool = same_role or [p for p in resumes if fit(p) >= MIN_FALLBACK_FIT and shared(p)]
    if not pool:
        return None
    best = max(pool, key=lambda p: (len(shared(p)), fit(p)))
    return best, shared(best)


# Display names for the shared-tool tokens in reasoning text.
_TOOL_NAMES = {
    "aws": "AWS", "gcp": "GCP", "ci": "CI", "cd": "CD", "sql": "SQL", "nosql": "NoSQL",
    "postgresql": "PostgreSQL", "mysql": "MySQL", "mongodb": "MongoDB", "graphql": "GraphQL",
    "api": "API", "apis": "APIs", "html": "HTML", "css": "CSS", "oauth": "OAuth", "sso": "SSO",
}  # fmt: skip


def fits_discipline(resume: dict, role_type: str) -> bool:
    """For a data/DevOps/mobile/frontend job: whether the resume is that kind of resume."""
    words = _DISCIPLINE_WORDS.get(role_type)
    text = f"{resume['name']} {resume['summary']}".lower()
    return words is None or bool(words.search(text))


def _names(resumes: list[dict]) -> str:
    return ", ".join(r["name"] for r in resumes)


# "Remote or Hybrid", "Hybrid/Remote", "On-site or remote": fully remote is one of the options.
_REMOTE_OPTION = re.compile(
    r"\bremote\s*(or|/)\s*(hybrid|on-?site|in-office|office)\b"
    r"|\b(hybrid|on-?site|in-office|office)\s*(or|/)\s*remote\b"
)


def remote_is_an_option(location_note: str) -> bool:
    return bool(_REMOTE_OPTION.search(location_note.lower()))


# A location that only names the country ("Job Locations US"): no office, so not on-site.
_COUNTRY_ONLY = re.compile(
    r"^(job\s*)?(locations?:?\s*)?(us|usa|u\.s\.a?\.?|united states( of america)?)\.?$",
    re.IGNORECASE,
)


def work_arrangement(response: AnalysisResponse) -> str:
    """The model's arrangement, corrected from its own location note: a JD offering remote as
    an option ("Remote or Hybrid work model") is remote, and hybrid/on-site with no location
    wording found, or only a country named, is a guess, so it's unknown (flagged, not
    skipped)."""
    note = response.location_note.strip()
    if response.work_arrangement not in ("hybrid", "onsite"):
        return response.work_arrangement
    if remote_is_an_option(note):
        return "remote"
    if note.lower() in _EMPTY_VALUES | {"not stated"} or _COUNTRY_ONLY.match(note):
        return "unknown"
    return response.work_arrangement


# The gender tag German, Austrian and Swiss postings add to the title by law: "(m/f/d)",
# "(m/w/d)", "(w/m/x)". A remote job with one is hired in that country, not in the US.
_DACH_TITLE_TAG = re.compile(r"\((?:[mwfdx]|div)(?:\s*/\s*(?:[mwfdx]|div|divers)){1,2}\)", re.I)


def non_us_by_text(response: AnalysisResponse, job_description: str) -> AnalysisResponse:
    """The model reads "work from wherever you like" as worldwide even when the JD is a
    German posting; the title tag settles it."""
    if response.remote_location == "non_us" or not _DACH_TITLE_TAG.search(job_description):
        return response
    return response.model_copy(update={"remote_location": "non_us"})


# Common short words of English and of the languages non-US postings come in (Spanish,
# Portuguese, German, French, Italian). A JD with more of the latter isn't a US job: the
# model calls a Spanish "remote-first" posting from Buenos Aires "worldwide" half the time.
_ENGLISH_WORDS = {
    "the", "and", "of", "to", "you", "with", "for", "our", "we", "is", "are", "will", "your",
}  # fmt: skip
_FOREIGN_WORDS = {
    "de", "la", "el", "los", "las", "para", "con", "una", "que", "del", "por", "y", "en",
    "da", "do", "em", "com", "você", "und", "der", "die", "das", "mit", "für", "wir", "ist",
    "sie", "eine", "le", "les", "et", "des", "pour", "avec", "vous", "nous", "est", "il", "di",
    "per", "che",
}  # fmt: skip


def written_in_english(job_description: str) -> bool:
    words = re.findall(r"[^\W\d_]+", job_description.lower())
    english = sum(w in _ENGLISH_WORDS for w in words)
    foreign = sum(w in _FOREIGN_WORDS for w in words)
    return foreign <= english


def skip_reason(response: AnalysisResponse) -> str | None:
    """The client only takes senior-enough, US-remote jobs. A reason to skip the job, or None.
    A JD that doesn't state its location isn't skipped (the UI flags it instead)."""
    where = response.location_note.strip()
    detail = f" ({where})" if where and where.lower() != "not stated" else ""
    if response.seniority == "intern":
        return "Internship role."
    if response.seniority == "junior":
        return "Junior / entry-level role."
    arrangement = work_arrangement(response)
    # Office-based first: the model tends to also flag "must be in Austin" as relocation.
    if arrangement == "hybrid":
        return f"Hybrid role, not fully remote{detail}."
    if arrangement == "onsite":
        return f"On-site role, not remote{detail}."
    if arrangement == "remote" and response.remote_location == "non_us":
        return f"Remote only outside the US{detail}."
    if response.relocation_required:
        return f"Requires relocation{detail}."
    return None


def decide_match(
    response: AnalysisResponse, job_description: str, resumes: list[dict]
) -> AnalysisResult:
    response = non_us_by_text(response, job_description)
    if response.role_type == "other" and _AI_TITLE.search(job_description):
        response = response.model_copy(update={"role_type": "ai"})
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
    backend = jd_backend(languages)
    backend_names = [t for t in languages if _families(_tokens(t)) & backend]
    options = language_options(languages, job_description)
    in_options = {lang for group in options for lang in group}
    # What the JD asks for: each option group counts once, like a single language.
    requirements = options + [[t] for t in core if t not in in_options]
    total = sum(_weight(group[0]) for group in requirements)

    # Everything below is measured from the resume text itself; the model's per-resume check
    # only breaks ties and vetoes a different kind of role when coverage is partial.
    scored = []  # (resume, overlap, coverage, same_backend, missing)
    for p in resumes:
        resume_tokens = _resume_tokens(p)
        overlap = [t for t in core if _named_in(t, resume_tokens)]
        if overlap:
            met = [g for g in requirements if any(t in overlap for t in g)]
            coverage = sum(_weight(g[0]) for g in met) / total
            same_backend = not backend or bool(resume_backend(p) & backend)
            missing = [
                g[0] if len(g) == 1 else f"one of {', '.join(g)}"
                for g in requirements
                if g not in met
            ]
            scored.append((p, overlap, coverage, same_backend, missing))
    with_backend = [s for s in scored if s[3]]

    def fit(p: dict) -> float:
        return checks[p["id"]].fit if p["id"] in checks else 0.0

    # For server-side jobs the backend language is the standard, so a resume with the JD's
    # backend (all of with_backend, when the JD names one) isn't vetoed by the model's role
    # guess. That includes "other" (a general Software Engineer or SDET job the model wouldn't
    # call backend). Mobile and frontend jobs keep the veto: an Android JD naming Java isn't a
    # Java backend job; data and DevOps jobs go by the discipline rule below.
    backend_decides = bool(backend) and response.role_type in ("backend", "fullstack", "other")
    # A different discipline (a Data Engineer job asking only for Python): sharing the stack
    # doesn't make a software engineering resume fit, so the model's role verdict is final.
    other_discipline = response.role_type in _DISCIPLINE_WORDS

    def role_ok(p: dict, coverage: float) -> bool:
        if other_discipline:
            return fits_discipline(p, response.role_type)
        same = p["id"] in checks and checks[p["id"]].same_role
        return same or coverage >= STRONG_COVERAGE or backend_decides

    candidates = [s for s in with_backend if role_ok(s[0], s[2])]

    def best_of(pool):
        # Most of the stack first; then more of the named terms (e.g. two of the languages a
        # JD accepts beats one), and only then the model's fit.
        return max(pool, key=lambda s: (s[2], len(s[1]), fit(s[0])))

    recommended, confidence = None, 0.0
    skip = skip_reason(response)
    if not skip and not written_in_english(job_description):
        skip = "The JD isn't in English, so it's not a US job."
    stack = ", ".join(core)
    role_name = _DISCIPLINE_NAMES.get(response.role_type, response.role_type)
    if skip:
        reasoning = f"Skipped: {skip}"
    elif not core:
        pick = _unnamed_language_pick(resumes, jd_tokens, response)
        if pick is None and response.role_type in _DISCIPLINE_WORDS:
            article = "an" if response.role_type == "ai" else "a"
            reasoning = (
                f"None of your resumes is for this kind of role ({article} {role_name} job), "
                "and the JD doesn't name a programming language."
            )
        elif pick is None:
            reasoning = "This JD doesn't name a programming language, and no resume fits it."
        else:
            best, tools = pick
            recommended = best["id"]
            # Lower than any named-stack match: nothing in the JD confirms the language.
            confidence = round(0.5 * fit(best), 2)
            names = [_TOOL_NAMES.get(t, t.capitalize()) for t in tools if t not in ("ci", "cd")]
            if {"ci", "cd"} <= set(tools):
                names.append("CI/CD")
            shared = ", ".join(names)
            reasoning = (
                "This JD doesn't name a backend language, so check it before applying. "
                f"{best['name']} is the closest fit"
                + (f", with {shared} from the JD." if shared else ".")
            )
    elif not scored:
        reasoning = f"None of your resumes include the stack this JD names ({stack})."
    elif not with_backend:
        best, overlap, *_ = best_of(scored)
        reasoning = (
            f"No resume has the backend language this JD needs ({', '.join(backend_names)}). "
            f"The closest, {best['name']}, only shares {', '.join(overlap)}."
        )
    elif not candidates:
        names = _names([s[0] for s in with_backend])
        verb = "has" if len(with_backend) == 1 else "have"
        reasoning = (
            f"{names} {verb} stack in common with this JD ({stack}), "
            f"but for a different kind of role than this {role_name} job."
        )
    else:
        best, overlap, coverage, _, missing = best_of(candidates)
        recommended = best["id"]
        confidence = round(0.7 * coverage + 0.3 * fit(best), 2)
        reasoning = f"{best['name']} has {', '.join(overlap)} from the stack this JD names" + (
            f"; missing {', '.join(missing)}." if missing else " (all of it)."
        )
        for group in options:
            if any(t in overlap for t in group):
                reasoning += f" The JD accepts any one of {', '.join(group)}."

    return AnalysisResult(
        jd_summary=response.jd_summary,
        role_type=response.role_type,
        work_arrangement=work_arrangement(response),
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
