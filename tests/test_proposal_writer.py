from proposal_writer import make_proposal


def test_personalizes_company_title_and_stack():
    lead = {
        "company": "Acme",
        "title": "Junior React Developer",
        "description": "React TypeScript REST API Redux",
    }
    text = make_proposal(lead)
    assert "Acme" in text
    assert "Junior React Developer" in text
    assert "React" in text
    assert "TypeScript" in text
    assert "REST API" in text
    assert "Redux Toolkit" in text


def test_uses_relevant_experience_from_description():
    lead = {
        "title": "Frontend Developer",
        "description": "Нужна адаптивная верстка по Figma и интеграция API",
    }
    text = make_proposal(lead)
    assert "Figma" in text
    assert "адаптив" in text.lower()
    assert "API" in text


def test_does_not_invent_company():
    lead = {"title": "Frontend Developer", "description": "React"}
    text = make_proposal(lead)
    assert text.startswith("Здравствуйте!")
