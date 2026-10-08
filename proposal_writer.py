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
    category = str(lead.get("category") or "").lower()

    from profit_ranker import FREELANCE_SOURCES
    if lead.get("source") in FREELANCE_SOURCES:
        skills = _skills(text) or ["HTML", "CSS", "JavaScript"]
        return (f"Здравствуйте! Готов выполнить задачу «{title}». "
                f"В собственных проектах работал с {', '.join(skills)}: адаптивные интерфейсы, "
                "API-интеграции, формы и обработка ошибок. "
                "Перед началом согласуем конкретный объём работ; результат проверю на разных размерах экрана.")

    if lead.get("language") == "en":
        greeting = f"Hello {company} team!" if company else "Hello!"
        if category == "qa":
            experience = ("I manually tested forms, API integrations, validation and error handling "
                          "in my own web applications, with frontend knowledge from React and TypeScript projects.")
        elif category == "layout":
            experience = "In my personal projects I built responsive interfaces using HTML, CSS/SCSS and JavaScript."
        else:
            skills = [KNOWN[k] for k in ("react", "typescript", "javascript", "redux", "html", "css") if k in text]
            stack = ", ".join(skills) or "React and TypeScript"
            experience = f"My personal projects use {stack}, REST API integrations, authentication, forms and error handling."
        return (f"{greeting} I am applying for the {title} position. {experience} "
                "I am based in Yekaterinburg, Russia, seeking remote work; my English level is B1. "
                "I would be happy to complete a relevant test task and discuss the role.")

    if category == "qa":
        greeting = f"Здравствуйте, команда {company}!" if company else "Здравствуйте!"
        return (
            f"{greeting} Вакансия «{title}» заинтересовала меня как Junior QA. "
            "В своих веб-проектах я вручную проверял формы, API-интеграции, валидацию и обработку ошибок; "
            "понимаю клиентскую часть приложений благодаря опыту с React и TypeScript. "
            "Готов работать удалённо, быстро включиться в процессы тестирования и выполнить тестовое задание."
        )

    skills = _skills(text) or ["React", "TypeScript", "HTML/CSS"]
    greeting = f"Здравствуйте, команда {company}!" if company else "Здравствуйте!"

    return (
        f"{greeting} Вакансия «{title}» мне подходит по стеку: {', '.join(skills)}. "
        f"В проектах я {_experience(text)}; готов работать удалённо и быстро включиться в задачи."
    )
