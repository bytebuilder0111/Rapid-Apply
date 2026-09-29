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
        "work_arrangement": "remote",
        "remote_location": "us",
        "relocation_required": False,
        "location_note": "Remote (US)",
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
    assert out.reasoning == (
        "iOS Mobile has Swift from the stack this JD names; missing Kotlin, Java."
    )


def test_same_language_on_a_different_platform_is_declined() -> None:
    # Java Backend has "Java" (half the stack), but the model judged it a different role.
    jd = "Android engineer: Kotlin and Java for our mobile app."
    response = _response(role_type="mobile", core=["Kotlin", "Java"], checks=_all_checks())
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id is None
    assert "Java Backend has part of the named stack" in out.reasoning
    assert "different kind of role than this mobile job" in out.reasoning


def test_no_resume_has_the_named_stack() -> None:
    jd = "Senior Python engineer building Django REST APIs."
    response = _response(
        core=["Python", "Django"], checks=_all_checks(java=_check("java", fit=0.8))
    )
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id is None
    assert out.reasoning == "None of your resumes include the stack this JD names (Python, Django)."


FULLSTACK_PROFILES = [
    {
        "id": "python",
        "name": "Python",
        "summary": "Full-stack engineer, Python/Django APIs with React front ends.",
        "skills": ["Python", "TypeScript", "Django", "React"],
    },
    {
        "id": "java",
        "name": "Java",
        "summary": "Senior engineer, Java and Spring Boot with React.",
        "skills": ["Java", "Spring Boot", "React"],
    },
    {
        "id": "node",
        "name": "Node",
        "summary": "Node.js and TypeScript engineer with React.",
        "skills": ["Node.js", "TypeScript", "React"],
    },
]
ARCHERA_JD = (
    "Senior Fullstack Software Engineer. React and TypeScript on the frontend, and Python "
    "API/service on the backend."
)


def _fullstack(**checks: ResumeCheck) -> AnalysisResponse:
    return _response(
        role_type="fullstack",
        core=["React", "TypeScript", "Python"],
        checks=[
            checks.get(p["id"], _check(p["id"], same_role=False, fit=0.1))
            for p in FULLSTACK_PROFILES
        ],
    )


def test_shared_framework_without_the_jds_language_never_wins() -> None:
    # The Archera case: the model rated Java well and flip-flopped on Python's role, but Java
    # only shares React while Python has everything the JD names.
    out = decide_match(
        _fullstack(java=_check("java", fit=0.9), python=_check("python", same_role=False, fit=0.5)),
        ARCHERA_JD,
        FULLSTACK_PROFILES,
    )
    assert out.recommended_resume_type_id == "python"
    assert out.reasoning == (
        "Python has React, TypeScript, Python from the stack this JD names (all of it)."
    )
    assert out.confidence == round(0.7 * 1.0 + 0.3 * 0.5, 2)


def test_most_of_the_named_stack_wins_over_the_models_fit() -> None:
    # Node has TypeScript + React (60%); Python has all of it despite a lower model fit.
    out = decide_match(
        _fullstack(node=_check("node", fit=0.9), python=_check("python", fit=0.4)),
        ARCHERA_JD,
        FULLSTACK_PROFILES,
    )
    assert out.recommended_resume_type_id == "python"


def test_only_a_framework_in_common_is_declined() -> None:
    profiles = [p for p in FULLSTACK_PROFILES if p["id"] == "java"]
    out = decide_match(
        _response(core=["React", "Python"], checks=[_check("java", fit=0.9)]),
        "React front end and Python services.",
        profiles,
    )
    assert out.recommended_resume_type_id is None
    assert out.reasoning.startswith("No resume has the backend language this JD needs (Python).")


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


JAVA_JD = "Senior Java Engineer: Spring Boot microservices."


def _java_candidate(**overrides) -> AnalysisResponse:
    return _response(core=["Java"], checks=_all_checks(java=_check("java")), **overrides)


def test_us_remote_senior_job_is_not_skipped() -> None:
    out = decide_match(_java_candidate(), JAVA_JD, PROFILES)
    assert out.skip_reason is None
    assert out.recommended_resume_type_id == "java"


def test_worldwide_remote_and_unstated_location_are_not_skipped() -> None:
    worldwide = _java_candidate(remote_location="worldwide", location_note="Remote, anywhere")
    unstated = _java_candidate(
        work_arrangement="unknown", remote_location="unknown", location_note="Not stated"
    )
    for response in (worldwide, unstated):
        assert decide_match(response, JAVA_JD, PROFILES).recommended_resume_type_id == "java"


def test_junior_and_intern_roles_are_skipped() -> None:
    junior = decide_match(_java_candidate(seniority="junior"), JAVA_JD, PROFILES)
    intern = decide_match(_java_candidate(seniority="intern"), JAVA_JD, PROFILES)
    assert junior.skip_reason == "Junior / entry-level role."
    assert intern.skip_reason == "Internship role."
    assert junior.recommended_resume_type_id is None and intern.recommended_resume_type_id is None


def test_hybrid_onsite_relocation_and_non_us_remote_are_skipped() -> None:
    cases = {
        "Hybrid role, not fully remote (Hybrid, 3 days in Austin).": _java_candidate(
            work_arrangement="hybrid", location_note="Hybrid, 3 days in Austin"
        ),
        "On-site role, not remote (New York, NY).": _java_candidate(
            work_arrangement="onsite", location_note="New York, NY"
        ),
        "Requires relocation (Remote after relocating to Toronto).": _java_candidate(
            relocation_required=True, location_note="Remote after relocating to Toronto"
        ),
        "Remote only outside the US (Remote - Canada).": _java_candidate(
            remote_location="non_us", location_note="Remote - Canada"
        ),
    }
    for expected, response in cases.items():
        out = decide_match(response, JAVA_JD, PROFILES)
        assert out.skip_reason == expected
        assert out.reasoning == f"Skipped: {expected}"
        assert out.recommended_resume_type_id is None
        assert out.confidence == 0.0


def test_version_numbers_do_not_block_a_match() -> None:
    jd = "Senior engineer: Java 17 and Spring Boot 3 microservices."
    response = _response(core=["Java 17", "Spring Boot 3"], checks=_all_checks())
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id == "java"


def test_a_framework_implies_its_language() -> None:
    profiles = [
        {"id": "dj", "name": "Django", "summary": "Django REST APIs.", "skills": ["Django"]}
    ]
    response = _response(core=["Python 3", "Django"], checks=[_check("dj", fit=0.8)])
    out = decide_match(response, "Python 3 and Django backend engineer.", profiles)
    assert out.recommended_resume_type_id == "dj"


def test_languages_are_found_even_if_the_model_misses_them() -> None:
    jd = "Senior Mobile Architect: native iOS and Android using Swift, Kotlin, Java."
    response = _response(
        role_type="mobile", core=[], checks=_all_checks(ios=_check("ios", fit=0.85))
    )
    out = decide_match(response, jd, PROFILES)
    assert out.jd_core_stack == ["Java", "Kotlin", "Swift"]
    assert out.recommended_resume_type_id == "ios"


def test_fallback_keeps_a_stackless_jd_empty() -> None:
    jd = STACKLESS_JD + " We go live weekly and our network is on .NET-free infra."
    out = decide_match(_response(core=[], checks=_all_checks()), jd, PROFILES)
    assert out.jd_core_stack == []


# The Avum SDET JD: the languages are options, and the model called it a different kind of role.
SDET_JD = """Software Development Engineer in Test (SDET), fully remote.
Proficiency in at least one object-oriented programming language, such as Java, Python, C#,
TypeScript, or JavaScript. Experience with the Page Object Model and CI/CD pipelines."""


def test_languages_listed_as_options_are_met_by_any_one() -> None:
    response = _response(
        role_type="other",
        core=["Java", "Python", "C#", "TypeScript"],
        checks=_all_checks(java=_check("java", same_role=False, fit=0.6)),
    )
    out = decide_match(response, SDET_JD, PROFILES)
    assert out.recommended_resume_type_id == "java"
    assert out.reasoning == (
        "Java Backend has Java from the stack this JD names (all of it). "
        "The JD accepts any one of Java, Python, C#, TypeScript."
    )


def test_options_do_not_excuse_a_separately_required_language() -> None:
    # "Python" is required on its own; only the front-end languages are options.
    jd = "Python backend is required. Front end in TypeScript or JavaScript."
    response = _response(core=["Python", "TypeScript", "JavaScript"], checks=_all_checks())
    out = decide_match(response, jd, PROFILES)
    # Node has TypeScript, but for a Python backend that's only the front end.
    assert out.recommended_resume_type_id is None
    assert out.reasoning.startswith("No resume has the backend language this JD needs (Python).")


def test_languages_joined_by_and_are_all_required() -> None:
    jd = "You will write Java and Python services every day."
    response = _response(
        core=["Java", "Python"], checks=_all_checks(java=_check("java", same_role=False))
    )
    out = decide_match(response, jd, PROFILES)
    assert out.recommended_resume_type_id is None  # half the stack, and a different role


# Lakeyth's real resumes: Python and C# also list TypeScript, for their React front ends.
LAKEYTH = [
    {
        "id": "python",
        "name": "Python",
        "summary": "Specializing in Python, TypeScript, and AWS; backend services and React.",
        "skills": ["Python", "TypeScript", "AWS", "Django", "FastAPI", "React", "PostgreSQL"],
    },
    {
        "id": "node",
        "name": "Node",
        "summary": "Specializing in Node.js, TypeScript, and AWS; backend services and React.",
        "skills": ["Node.js", "TypeScript", "React", "AWS", "PostgreSQL", "GraphQL"],
    },
    {
        "id": "csharp",
        "name": "C#",
        "summary": "ASP.NET Core and React. Proficient in C#, TypeScript, and SQL.",
        "skills": ["C#", "ASP.NET Core", "React", "TypeScript", "SQL Server", "Azure"],
    },
    {
        "id": "go",
        "name": "GoLang",
        "summary": "Go and distributed systems. PostgreSQL, Kafka, and AWS.",
        "skills": ["Go", "PostgreSQL", "Kafka", "AWS"],
    },
]


def test_typescript_only_job_is_a_node_backend() -> None:
    # Tru Treasury: "built primarily with TypeScript, Next.js, PostgreSQL, and AWS".
    jd = "Senior Full Stack Developer. Our stack: TypeScript, Next.js, React, PostgreSQL, AWS."
    checks = [_check(p["id"], fit=0.9 if p["id"] == "python" else 0.7) for p in LAKEYTH]
    out = decide_match(
        _response(role_type="fullstack", core=["TypeScript", "Next.js"], checks=checks),
        jd,
        LAKEYTH,
    )
    assert out.recommended_resume_type_id == "node"


def test_a_resume_is_judged_by_its_named_backend() -> None:
    # "GoLang" names the backend even though the resume text says "Go".
    jd = "Backend engineer writing Golang services."
    out = decide_match(_response(core=["Golang"], checks=[_check("go")]), jd, LAKEYTH)
    assert out.recommended_resume_type_id == "go"
