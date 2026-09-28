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


def test_link_copies_with_layout_or_tracking_params_match() -> None:
    assert normalize_link(
        "https://careers-x.icims.com/jobs/12/job?jr_id=abc&mobile=false&width=1296&height=500"
    ) == normalize_link("https://careers-x.icims.com/jobs/12/job?width=768")


def test_greenhouse_embed_link_matches_direct_link() -> None:
    embed = "https://job-boards.greenhouse.io/embed/job_app?for=evio&jr_id=6a9b&token=4731447005"
    assert normalize_link(embed) == normalize_link(
        "https://job-boards.greenhouse.io/evio/jobs/4731447005"
    )


def test_company_punctuation_and_possessive_are_ignored() -> None:
    sheet = [Entry("Samsara", "Senior Software Engineer II", "", "row 2")]
    reason = find_duplicate(
        sheet, company="Samsara’s", position="Senior Software Engineer II", job_link="https://n.io"
    )
    assert reason is not None
