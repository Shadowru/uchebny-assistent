"""
title: МЭШ-гейт учебных запросов
description: Отклоняет неучебные запросы (вопросы о модели, политика и т.п.) до обращения к LLM.
version: 0.1
"""

import re

from pydantic import BaseModel, Field

# Регулярные выражения (через ;) — вопросы «кто ты / какая модель», попытки
# вытащить инструкции, неоднозначные слова, которым нужна точная форма.
DEFAULT_PATTERNS = ";".join(
    [
        r"^\s*(а\s+)?(кто|что)\s+(ты|вы)\b",
        r"\bты\s+кто\b",
        r"\bкак(ая|ой|ую)\s+(ты\s+|у\s+тебя\s+)?(модель|модели|ллм|нейросет)",
        r"\bчто\s+за\s+(модель|нейросет|ллм)",
        r"\bна\s+как(ой|ую)\s+(модел|технолог|нейросет)",
        r"\bкто\s+тебя\s+(создал|сделал|обучил|разработал)",
        r"\bсистемн\w*\s+промпт",
        r"\bsystem\s+prompt",
        r"\bignore\s+(previous|all)\s+instruction",
        r"\bигнорируй\s+(предыдущие\s+)?инструкции",
        r"\bgpt\b|\bchatgpt\b|\bopenai\b|\bclaude\b|\banthropic\b|\bllm\b",
        r"\bджипити\b|\bчат\s?жпт\b|\bопена[ий]\b|\bклод\b",
        r"\bвыбор(ы|ов|ах|ам|ами)\b",
        r"\blgbt\b|\bgay\b|\bsex\w*|\bporn\w*|\bwar\b",
        # точные формы, где корень дал бы ложные срабатывания
        # (гейзер, счётчик Гейгера, трамплин)
        r"\bге(й|я|ю|и|ев|ям|ями|ях)\b",
        r"\bтрамп(?!лин)",
        r"\bсво\b",
    ]
)

# Корни слов (через ;) — запретные темы; совпадение по началу слова.
# Блокируются всегда, независимо от контекста.
DEFAULT_ROOTS = ";".join(
    [
        "политик", "политич", "президент", "путин", "зеленск", "байден",
        "навальн", "оппозиц", "митинг", "протест",
        "спецоперац", "мобилизац", "нато", "санкци",
        "лгбт", "лесби", "гомосекс", "бисексу",
        "трансгендер", "квир", "секс", "эротик", "порно", "интим",
        "наркот", "суицид", "самоубийств",
        "террор", "экстремизм", "взрывчат", "казино",
    ]
)

# Условные корни: блокируются, только если в запросе НЕТ учебного контекста.
# Так «план урока: Великая Отечественная война» проходит,
# а «расскажи про войну на Украине» — нет.
DEFAULT_CONDITIONAL_ROOTS = ";".join(["война", "войн", "военн", "украин"])

# Маркеры учебного контекста (корни): наличие любого «разрешает» условные темы.
DEFAULT_EDU_MARKERS = ";".join(
    [
        "урок", "класс", "школьн", "ученик", "учебн", "задани",
        "рабоч", "контрольн", "проверочн", "викторин", "тест",
        "разминк", "домашн", "методич", "преподава", "фгос",
        "объясн", "конспект", "презентаци", "программ",
    ]
)

DEFAULT_REJECT = (
    "Этот запрос не относится к учебным задачам, и ассистент его не обрабатывает. "
    "Я помогаю готовить уроки: план, объяснение темы, задания, проверка работ. "
    "Сформулируйте, пожалуйста, учебный запрос."
)


class Filter:
    class Valves(BaseModel):
        blocked_patterns: str = Field(
            default=DEFAULT_PATTERNS,
            description="Регулярные выражения через ';' — запрос отбивается при совпадении",
        )
        blocked_roots: str = Field(
            default=DEFAULT_ROOTS,
            description="Корни слов через ';' — запрос отбивается, если слово начинается с корня",
        )
        conditional_roots: str = Field(
            default=DEFAULT_CONDITIONAL_ROOTS,
            description="Корни через ';' — отбиваются только без учебного контекста",
        )
        edu_markers: str = Field(
            default=DEFAULT_EDU_MARKERS,
            description="Корни-маркеры учебного контекста через ';' — разрешают условные темы",
        )
        reject_message: str = Field(
            default=DEFAULT_REJECT,
            description="Сообщение, которое видит пользователь вместо ответа",
        )
        skip_admin: bool = Field(default=True, description="Не проверять администраторов")

    def __init__(self):
        self.valves = self.Valves()

    def _last_user_text(self, body):
        for m in reversed(body.get("messages", [])):
            if m.get("role") == "user":
                c = m.get("content")
                if isinstance(c, list):
                    return " ".join(
                        p.get("text", "") for p in c if isinstance(p, dict)
                    )
                return c or ""
        return ""

    def inlet(self, body: dict, __user__: dict = None) -> dict:
        if self.valves.skip_admin and __user__ and __user__.get("role") == "admin":
            return body
        text = (self._last_user_text(body) or "").lower().replace("ё", "е")
        if not text:
            return body
        for pat in self.valves.blocked_patterns.split(";"):
            pat = pat.strip()
            if pat and re.search(pat, text, re.IGNORECASE):
                raise Exception(self.valves.reject_message)
        for root in self.valves.blocked_roots.split(";"):
            root = root.strip().lower()
            if root and re.search(r"\b" + re.escape(root), text, re.IGNORECASE):
                raise Exception(self.valves.reject_message)
        # условные темы: пропускаем только при учебном контексте
        has_edu = any(
            re.search(r"\b" + re.escape(m.strip().lower()), text)
            for m in self.valves.edu_markers.split(";")
            if m.strip()
        )
        if not has_edu:
            for root in self.valves.conditional_roots.split(";"):
                root = root.strip().lower()
                if root and re.search(r"\b" + re.escape(root), text, re.IGNORECASE):
                    raise Exception(self.valves.reject_message)
        return body
