"""Create truthful, compact proposals without inventing experience."""
import re

KNOWN={
 "react":"React","typescript":"TypeScript","javascript":"JavaScript",
 "html":"HTML","css":"CSS","scss":"SCSS","redux":"Redux Toolkit",
 "figma":"Figma","rest":"REST API","git":"Git"
}

def make_proposal(lead):
    text=(" ".join(str(lead.get(k) or "") for k in ("title","description"))).lower()
    skills=[v for k,v in KNOWN.items() if k in text][:5]
    stack=", ".join(skills) or "React, TypeScript, HTML/CSS"
    title=re.sub(r"\s+"," ",str(lead.get("title") or "задача")).strip()
    return (
      f"Здравствуйте! Готов выполнить задачу «{title}». "
      f"Работаю с {stack}; могу аккуратно реализовать адаптивный интерфейс и интеграцию с API, если она требуется. "
      "Перед началом уточню только необходимые технические детали и сразу приступлю. "
      "Срок и стоимость подтвержу по полному объёму задачи."
    )
