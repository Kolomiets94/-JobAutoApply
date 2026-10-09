from profit_ranker import rank_lead


def test_excludes_unmatched_frameworks_and_mobile_stacks():
    for stack in ("Vue", "Angular", "Full Stack", "React Native", "Flutter"):
        lead = rank_lead({"source": "hh", "title": "Junior React Developer",
                          "description": "Required: " + stack})
        assert not lead["eligible"], stack


def test_accepts_explicit_one_year_frontend_and_rejects_higher_experience():
    base = {"source": "hh", "title": "Frontend React Developer", "description": "React TypeScript"}
    assert rank_lead({**base, "experience": "от 1 года"})["eligible"]
    assert not rank_lead({**base, "experience": "от 3 лет"})["eligible"]
    assert not rank_lead({**base, "experience": "от 1 года", "title": "Middle Frontend React Developer"})["eligible"]


def test_excludes_internship_even_when_title_says_junior():
    lead = rank_lead({"source": "hh", "title": "Junior React internship", "description": "React"})
    assert not lead["eligible"]
