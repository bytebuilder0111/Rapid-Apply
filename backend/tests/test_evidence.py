from app.ai.evidence import decide_match
from app.ai.schemas import AnalysisResponse, ResumeCheck

PROFILES = [
    {
        "id": "node",
        "name": "Node",
        "summary": "Senior software engineer with Node.js and TypeScript, AWS, PostgreSQL.",
        "skills": ["Node.js", "TypeScript", "AWS", "PostgreSQL", "CI/CD"],
    },
    {
        "id": "java",
        "name": "Java Backend",
        "summary": "Backend engineer, Java 17 and Spring Boot microservices.",
        "skills": ["Java", "Spring Boot", "Kafka"],
    },
    {
        "id": "ios",
        "name": "iOS Mobile",
        "summary": "iOS engineer building apps in Swift and SwiftUI.",
        "skills": ["Swift", "SwiftUI", "Objective-C"],
    },
]

# The "Senior Full-Stack & Cloud Engineer" JD: no language or framework named anywhere.
STACKLESS_JD = """Senior Full-Stack & Cloud Engineer. Take ownership of an internally developed
web application. Strong full-stack development capabilities using modern web technologies.
Experience deploying in a major cloud. Working knowledge of relational databases. CI/CD and
Git workflows."""


def _check(pid: str, *, same_role: bool = True, fit: float = 0.9) -> ResumeCheck:
    return ResumeCheck(
        resume_id=pid, matching_technologies=[], same_role=same_role, fit=fit, note=f"{pid} note."
    )


def _response(*, core: list[str], checks: list[ResumeCheck], **overrides) -> AnalysisResponse:
    base = {
        "jd_summary": "s",
        "role_type": "backend",
        "jd_core_stack": core,
        "main_backend_skill": core[0] if core else "Not specified",
        "backend_framework": None,
        "secondary_skills": [],
        "seniority": "senior",
        "key_requirements": [],
        "resume_checks": checks,
    }
    return AnalysisResponse(**(base | overrides))


def _all_checks(**per_id) -> list[ResumeCheck]:
    return [per_id.get(p["id"], _check(p["id"], same_role=False, fit=0.1)) for p in PROFILES]


def test_stack_the_jd_never_names_is_dropped_and_declined() -> None:
    # The model read "TypeScript" into a JD that never mentions it and liked the Node resume.
    response = _response(
        role_type="fullstack",
        core=["TypeScript"],
        main_backend_skill="TypeScript",
        backend_framework="null",
        checks=_all_checks(node=_check("node")),
    )
    out = decide_match(response, STACKLESS_JD, PROFILES)
    assert out.jd_core_stack == []
    assert out.recommended_resume_type_id is None
    assert out.confidence == 0.0
    assert out.main_backend_skill == "Not specified"
    assert out.backend_framework is None
    assert "doesn't name a specific programming language" in out.reasoning


def test_generic_tools_never_count_as_core_stack() -> None:
    # CI/CD and Git appear in the JD and on the Node resume, but that's incidental overlap.
    response = _response(core=["CI/CD", "Git"], checks=_all_checks(node=_check("node")))
    out = decide_match(response, STACKLESS_JD, PROFILES)
    assert out.jd_core_stack == []
    assert out.recommended_resume_type_id is None


def test_code_finds_the_match_the_model_can_only_assess() -> None:
    jd = "Senior Mobile Architect: native iOS and Android using Swift, Kotlin, Java."
    response = _response(
        role_type="mobile",
        core=["Swift", "Kotlin", "Java"],
        checks=_all_checks(ios=_check("ios", fit=0.85)),
    )
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id == "ios"
    assert out.confidence == 0.85
    assert out.reasoning == "ios note. Matches on: Swift."


def test_same_language_on_a_different_platform_is_declined() -> None:
    # Java Backend has "Java", but the model judged it a different role from Android.
    jd = "Android engineer: Kotlin and Java for our mobile app."
    response = _response(role_type="mobile", core=["Kotlin", "Java"], checks=_all_checks())
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id is None
    assert "Java Backend shares part of the named stack" in out.reasoning
    assert "different kind of role than this mobile job" in out.reasoning


def test_no_resume_has_the_named_stack() -> None:
    jd = "Senior Python engineer building Django REST APIs."
    response = _response(
        core=["Python", "Django"], checks=_all_checks(java=_check("java", fit=0.8))
    )
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id is None
    assert out.reasoning == "None of your resumes include the stack this JD names (Python, Django)."


def test_weak_fit_is_declined_even_with_stack_and_role() -> None:
    jd = "Node.js engineer for embedded firmware tooling."
    response = _response(core=["Node.js"], checks=_all_checks(node=_check("node", fit=0.3)))
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id is None
    assert out.reasoning.startswith("The closest resume, Node, fits only 30%.")


def test_highest_fit_candidate_wins() -> None:
    jd = "Backend: Java with Spring Boot, or Node.js with TypeScript."
    response = _response(
        core=["Java", "Spring Boot", "Node.js", "TypeScript"],
        checks=_all_checks(node=_check("node", fit=0.7), java=_check("java", fit=0.9)),
    )
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id == "java"
    assert out.reasoning.endswith("Matches on: Java, Spring Boot.")


def test_java_does_not_match_javascript() -> None:
    jd = "Backend role: JavaScript services."
    response = _response(core=["JavaScript"], checks=_all_checks(java=_check("java")))
    assert decide_match(response, jd, PROFILES).recommended_resume_type_id is None


def test_spelling_variants_still_match() -> None:
    jd = "We use NodeJS and Postgres."
    response = _response(core=["NodeJS"], checks=_all_checks(node=_check("node")))
    assert decide_match(response, jd, PROFILES).recommended_resume_type_id == "node"


def test_multi_word_framework_needs_every_word_in_the_jd() -> None:
    jd = "Java developer. Spring experience a plus."
    response = _response(core=["Java", "Spring Boot"], checks=_all_checks(java=_check("java")))
    out = decide_match(response, jd, PROFILES)
    assert out.jd_core_stack == ["Java"]
    assert out.recommended_resume_type_id == "java"
