"""Create truthful, concise, individualized cover letters."""

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
    ("api", "делал интеграции с REST API и обработку ошибок"),
    ("auth", "реализовывал авторизацию и защищённые маршруты"),
    ("login", "реализовывал авторизацию и защищённые маршруты"),
    ("redux", "работал с Redux Toolkit"),
    ("figma", "переносил интерфейсы из Figma в адаптивную вёрстку"),
    ("responsive", "делал адаптивные интерфейсы"),
    ("адаптив", "делал адаптивные интерфейсы"),
    ("search", "реализовывал поиск с debounce"),
    ("поиск", "реализовывал поиск с debounce"),
    ("validation", "добавлял валидацию и обработку ошибок"),
    ("валидац", "добавлял валидацию и обработку ошибок"),
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
    return found[:4]


def _experience(text):
    for marker, sentence in PROJECT_EXAMPLES:
        if marker in text:
            return sentence
    return "работал с React, TypeScript, адаптивной вёрсткой и API"


def make_proposal(lead):
    title = _clean(lead.get("title") or "Frontend-разработчик")
    company = _company(lead)
    description = _clean(lead.get("description"))
    text = f"{title} {description}".lower()

    skills = _skills(text) or ["React", "TypeScript", "HTML/CSS"]
    greeting = f"Здравствуйте, команда {company}!" if company else "Здравствуйте!"

    return (
        f"{greeting} Вакансия «{title}» мне подходит по стеку: {', '.join(skills)}. "
        f"В проектах я {_experience(text)}; готов работать удалённо и быстро включиться в задачи."
    )
