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
