from app.analysis.duplicates import Entry, find_duplicate, normalize_link

SHEET = [
    Entry(
        company="Turing",
        position="Software Engineer",
        job_link="https://turing.betterteam.com/software-engineer",
        where="row 2 of Bid Sheet - ALL > Donzell-Auto",
    ),
    Entry(
        company="Whatnot",
        position="Senior Software Engineer, Logistics",
        job_link="https://jobs.ashbyhq.com/whatnot/123?utm_source=linkedin",
        where="row 3 of Bid Sheet - ALL > Donzell-Auto",
    ),
]


def _dup(company: str, position: str, link: str) -> str | None:
    return find_duplicate(SHEET, company=company, position=position, job_link=link)


def test_link_variants_normalize_to_the_same_key() -> None:
    key = "jobs.ashbyhq.com/whatnot/123"
    assert normalize_link("https://jobs.ashbyhq.com/whatnot/123/") == key
    assert normalize_link("http://www.JOBS.ashbyhq.com/whatnot/123#apply") == key
    assert normalize_link("jobs.ashbyhq.com/whatnot/123?utm_source=x&ref=y") == key
    assert normalize_link("https://x.com/job?id=5&utm_campaign=z") == "x.com/job?id=5"


def test_same_job_link_is_a_duplicate() -> None:
    reason = _dup("Other Co", "Other Role", "http://www.jobs.ashbyhq.com/whatnot/123/")
    assert reason == "This job link is already recorded (row 3 of Bid Sheet - ALL > Donzell-Auto)."


def test_same_company_and_position_is_a_duplicate() -> None:
    reason = _dup("  turing ", "software   ENGINEER", "https://turing.example/new-link")
    assert reason is not None
    assert reason.endswith("is already recorded (row 2 of Bid Sheet - ALL > Donzell-Auto).")


def test_same_company_other_position_is_not_a_duplicate() -> None:
    assert _dup("Turing", "Backend Engineer", "https://turing.example/backend") is None


def test_a_different_query_id_is_a_different_job() -> None:
    sheet = [Entry("A", "B", "https://x.com/job?id=5", "row 2")]
    assert (
        find_duplicate(sheet, company="C", position="D", job_link="https://x.com/job?id=6") is None
    )
