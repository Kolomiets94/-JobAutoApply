"""Create truthful, individualized cover letters without inventing experience."""

import re


KNOWN = {
    "react": "React",
    "typescript": "TypeScript",
    "javascript": "JavaScript",
    "html": "HTML",
    "css": "CSS",
    "scss": "SCSS",
    "redux": "Redux Toolkit",
    "figma": "Figma",
    "rest": "REST API",
    "git": "Git",
    "vite": "Vite",
    "webpack": "Webpack",
    "api": "API",
    "responsive": "адаптивная вёрстка",
    "адаптив": "адаптивная вёрстка",
    "кроссбрауз": "кроссбраузерная вёрстка",
}

PROJECT_EXAMPLES = (
    ("api", "делал интеграции с REST API, обработку ошибок и состояния загрузки"),
    ("auth", "реализовывал авторизацию и защищённые маршруты"),
    ("login", "реализовывал авторизацию и защищённые маршруты"),
    ("redux", "работал с Redux Toolkit для управления состоянием"),
    ("figma", "переносил интерфейсы из Figma в адаптивную вёрстку"),
    ("responsive", "делал адаптивные интерфейсы под разные экраны"),
    ("адаптив", "делал адаптивные интерфейсы под разные экраны"),
    ("search", "реализовывал поиск с debounce"),
    ("поиск", "реализовывал поиск с debounce"),
    ("validation", "добавлял валидацию форм и обработку ошибок"),
    ("валидац", "добавлял валидацию форм и обработку ошибок"),
)


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _company(lead):
    return _clean(
        lead.get("company")
        or lead.get("employer")
        or lead.get("company_name")
        or ""
    )


def _skills(text):
    found = []
    for key, label in KNOWN.items():
        if key in text and label not in found:
            found.append(label)
    return found[:5]


def _relevant_experience(text):
    examples = []
    for marker, sentence in PROJECT_EXAMPLES:
        if marker in text and sentence not in examples:
            examples.append(sentence)
    return examples[:2]


def make_proposal(lead):
    title = _clean(lead.get("title") or "Frontend-разработчик")
    company = _company(lead)
    description = _clean(lead.get("description"))
    text = f"{title} {description}".lower()

    skills = _skills(text)
    if not skills:
        skills = ["React", "TypeScript", "HTML/CSS"]

    experience = _relevant_experience(text)

    greeting = f"Здравствуйте, команда {company}!" if company else "Здравствуйте!"
    vacancy_ref = f"Вакансия «{title}» заинтересовала меня"
    skill_sentence = (
        " потому что в ней хорошо совпадает мой стек: "
        + ", ".join(skills)
        + "."
    )

    if experience:
        experience_sentence = (
            " В своих проектах я "
            + " и ".join(experience)
            + "."
        )
    else:
        experience_sentence = (
            " В учебных и пет-проектах я работал с React и TypeScript, "
            "делал адаптивные интерфейсы, интеграцию с API, формы и обработку ошибок."
        )

    closing = (
        " Готов работать удалённо, быстро включиться в задачу и выполнить тестовое задание. "
        "Буду рад обсудить детали."
    )

    return greeting + " " + vacancy_ref + skill_sentence + experience_sentence + closing
