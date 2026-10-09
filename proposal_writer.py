"""Short, truthful, role-specific applications based on the candidate's actual projects."""

import re
from profit_ranker import FREELANCE_SOURCES, _role_category


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def make_proposal(lead):
    title = _clean(lead.get("title") or "вакансия")
    description = _clean(lead.get("description"))
    category = _role_category(lead)
    freelance = str(lead.get("source") or "").lower() in FREELANCE_SOURCES
    english = lead.get("language") == "en"
    context = f"{title} {description}".lower()
    company = _clean(lead.get("company") or lead.get("employer") or lead.get("company_name"))
    greeting = f"Здравствуйте, команда {company}!" if company else "Здравствуйте!"
    stack_extra = " Также работал с Redux Toolkit." if "redux" in context else ""
    layout_extra = " Использую Figma для работы с макетами." if "figma" in context else ""

    if freelance:
        if english:
            if "react" in context:
                return (f"Hello! I can help with {title}. I've built React and TypeScript projects "
                        "with responsive UI, forms and API integration. I can clarify the scope "
                        "and estimate a realistic delivery time before starting.")
            return (f"Hello! I'm interested in {title}. My experience includes JavaScript, "
                    "HTML/CSS, responsive layouts and API integrations in personal projects. "
                    "I can review the requirements and agree on deliverables and timing.")
        if "react" in context:
            return (f"Здравствуйте! Готов обсудить задачу «{title}». "
                    "Разрабатывал проекты на React и TypeScript: формы, API, адаптивные интерфейсы. "
                    "Предлагаю сначала уточнить объём работ и согласовать срок.")
        return (f"Здравствуйте! Заинтересовал заказ «{title}». "
                "Делал адаптивные страницы на HTML/CSS и JavaScript, работал с формами и API. "
                "Готов уточнить требования и предложить срок выполнения.")

    if english:
        if category == "layout":
            return (f"Hello! I'm applying for the {title} role. I build responsive pages "
                    "with HTML, CSS/SCSS and JavaScript in my own projects. "
                    "I'm available for remote work and can share examples on GitHub.")
        if category == "qa":
            return (f"Hello! I'm interested in the {title} role. I manually tested forms, "
                    "validation and API interactions in my own web applications. "
                    "My React and TypeScript background helps me investigate frontend bugs.")
        return (f"Hello! I'm applying for the {title} role. My React and TypeScript projects "
                "include API integration, authentication, CRUD, responsive layouts and form validation. "
                "I'm available for remote work and can share my GitHub projects.")

    if category == "layout":
        return (f"{greeting} Откликаюсь на вакансию «{title}». "
                "Верстаю адаптивные страницы на HTML, CSS/SCSS и JavaScript, "
                "работаю с Figma и Git. Готов показать примеры проектов и выполнить тестовое задание.")
    if category == "qa":
        return (f"{greeting} Откликаюсь на вакансию «{title}». "
                    "В своих веб-проектах вручную проверял формы, валидацию, API и обработку ошибок. "
                "Знаю React и TypeScript, поэтому понимаю поведение клиентской части. "
                "Готов выполнить тестовое задание на позицию Junior.")
    return (f"{greeting} Откликаюсь на вакансию «{title}». "
                "В проектах на React и TypeScript реализовал авторизацию, CRUD, "
            "интеграцию с REST API, адаптивную вёрстку и валидацию форм. "
            "Готов показать код на GitHub и выполнить тестовое задание." + stack_extra + layout_extra)
