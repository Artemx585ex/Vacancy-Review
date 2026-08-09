#!/usr/bin/env python3
"""Проверяет скачанные вакансии (vacancies/*.md) по гайду карьерного сайта Авито.

Для каждой вакансии и каждого критерия выставляет статус светофора:
  green  — замечаний нет;
  yellow — эвристика или некритичное замечание, стоит посмотреть глазами;
  red    — явное нарушение гайда.

Результат: report.json (для генерации сайта) и краткая сводка в stdout.

Использование:
    python3 check_vacancy.py [-d vacancies] [-o report.json]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

# ---------- разбор md-файла ----------

def parse_md(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8")
    meta = {}
    body = text
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if m:
        body = text[m.end():]
        for line in m.group(1).splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    sections = []
    current = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = {"heading": line[3:].strip(), "items": [], "paragraphs": []}
            sections.append(current)
        elif line.startswith("- ") and current:
            current["items"].append(line[2:].strip())
        elif line.strip() and not line.startswith("# ") and current:
            current["paragraphs"].append(line.strip())
    return {"meta": meta, "body": body, "sections": sections, "file": path.name}


def find_section(vac: dict, *keywords: str) -> dict | None:
    for s in vac["sections"]:
        h = s["heading"].lower()
        if any(k in h for k in keywords):
            return s
    return None


# ---------- критерии ----------
# каждая функция возвращает список (severity, comment) или (severity, comment, quote),
# где quote — точная цитата из текста вакансии для подсветки на сайте (#:~:text=)

CLICHES = re.compile(
    r"\bданн(?:ый|ая|ое|ого|ой|ую|ом)\b|молод(?:ой|ым)\s+и\s+дружн|дружн\w+\s+коллектив"
    r"|печеньк|гор(?:еть|ите|ящих)\s+идее|доставк\w+\s+проектов|чай,\s*кофе"
    r"|команд\w+\s+мечты|динамично\s+развива|пенетраци|селлер",
    re.I,
)

# Признаки обязательных требований, по которым работодатель может обоснованно
# принять решение по кандидату. Отсутствие таких признаков требует проверки ИИ.
CONCRETE_REQUIREMENT = re.compile(
    r"\d+\s*(?:год|лет|года)|опыт|знани|владен|образован|"
    r"сертификат|английск|инструмент|программ|sql|python|excel|pn[l]?|api",
    re.I,
)

YO_WORDS = re.compile(
    r"\b(ждем|еще|партнер\w*|отчет\w*|учет\w*|объем\w*|серьезн\w*|надежн\w*)\b"
)

BENEFIT_BLOCKS = [
    ("расширенная забота о здоровье (ДМС, страхование жизни, онкострахование)",
     re.compile(r"ДМС|онкострахован|страхование жизни", re.I)),
    ("сервисы психологической поддержки и консультации",
     re.compile(r"психологическ\w+ поддержк|ЗОЖ[‑-]консультац", re.I)),
    ("корпоративный спорт",
     re.compile(r"корпоративн\w+ спорт|спортзал|групповые тренировк|велбиинг", re.I)),
    ("спецпредложения партнёров и скидки на сервисы Авито",
     re.compile(r"спецпредложени|скидки на сервисы Авито|скидки от партн", re.I)),
    ("компенсация питания",
     re.compile(r"компенсаци\w+ питани", re.I)),
]

ADDITIONAL_REQUIREMENT = re.compile(
    r"\b(?:желательно|будет\s+(?:здорово|плюсом)|плюсом|преимуществом)\b", re.I
)
# В блоке «Будет здорово, если вы» формулировка «будет плюсом» создаёт
# ненужный второй уровень дополнительных требований. Это замечание, но не
# критичная ошибка: сам дополнительный блок существует и читается корректно.
NESTED_ADDITIONAL_REQUIREMENT = re.compile(
    r"\b(?:желательно|будет\s+плюсом|плюсом|преимуществом)\b", re.I
)
PRODUCT_TECH_DIRECTIONS = {
    "управление продуктом", "разработка", "data science", "дизайн",
    "информационная безопасность",
}

def check_title(vac):
    out = []
    title = vac["meta"].get("title", "")
    if re.search(r"[()]", title):
        out.append(("yellow", f"скобки в названии: «{title}» — гайд советует избегать скобок (2.4 п. 4)", title))
    latin = re.findall(r"[A-Za-z][A-Za-z&-]+", title)
    role_words = {"manager", "senior", "junior", "lead", "head", "developer", "engineer",
                  "designer", "analyst", "director", "specialist", "product", "project", "owner"}
    bad = [w for w in latin if w.lower() in role_words]
    if bad:
        out.append(("yellow", f"должность латиницей в названии: {', '.join(bad)} — название пишется по-русски (2.1)", title))
    return out


def check_discrimination(vac):
    out = []
    body = vac["body"]
    for pat, what in [
        (r"не\s+старше\s+\d+|моложе\s+\d+|возраст\w*\s+(?:до|от)\s+\d+", "возраст"),
        (r"\bмужчин\w*\b|\bженщин\w*\b", "пол"),
        (r"\bнациональност\w*\b", "национальность"),
        (r"\bрелиги\w*\b", "религия"),
        (r"\bгражданств\w*\b", "гражданство"),
    ]:
        for m in re.finditer(pat, body, re.I):
            out.append(("red", f"дискриминационное требование ({what}): «…{context(body, m)}…» — ст. 3 и 64 ТК РФ",
                        frag(body, m)))
    return out


def check_structure(vac):
    out = []
    sections = vac["sections"]
    # «Примеры будущих задач» — отдельный необязательный блок. Он не заменяет
    # обязательные обязанности / «Какие задачи вас ждут».
    tasks = find_section(vac, "задачи вас ждут", "предстоит заниматься")
    requirements = find_section(vac, "ждем, что вы", "ждём, что вы", "требован")
    benefits = find_section(vac, "работа у нас", "условия")
    if not tasks:
        # Несуществующий блок подсветить нельзя: ведём к ближайшему разделу.
        near = requirements or benefits or (sections[0] if sections else None)
        out.append(("red", "нет блока задач («Какие задачи вас ждут»)",
                    near["heading"] if near else None))
    if not requirements:
        near = tasks or benefits or (sections[0] if sections else None)
        out.append(("red", "нет блока требований («Мы ждём, что вы»)",
                    near["heading"] if near else None))
    if not benefits:
        near = requirements or tasks or (sections[-1] if sections else None)
        out.append(("red", "нет блока условий («Работа у нас — это»)",
                    near["heading"] if near else None))

    # По таблице «желательно» и похожие дополнительные требования должны быть
    # вынесены из обязательного блока в отдельный раздел.
    if requirements:
        for item in requirements["items"] + requirements["paragraphs"]:
            match = ADDITIONAL_REQUIREMENT.search(item)
            if match:
                out.append((
                    "red",
                    f"дополнительное требование в обязательном блоке: «{shorten(item)}» — вынесите его в «Будет здорово, если вы»",
                    item,
                ))

    # В дополнительном блоке не нужны ещё одни «дополнительные» требования:
    # «Будет плюсом» и «желательно» следует сформулировать как обычный пункт.
    nice_sections = [s for s in sections if "будет здорово" in s["heading"].lower()]
    for nice in nice_sections:
        for item in nice["items"] + nice["paragraphs"]:
            if NESTED_ADDITIONAL_REQUIREMENT.search(item):
                out.append((
                    "yellow",
                    f"повторное дополнительное требование в блоке «Будет здорово, если вы»: «{shorten(item)}» — уберите «будет плюсом» / «желательно»",
                    item,
                ))

    # Один и тот же дополнительный блок не должен идти подряд дважды.
    # Показываем каждый повтор, чтобы редактору было понятно, какой заголовок
    # нужно объединить с предыдущим блоком.
    for nice in nice_sections[1:]:
        out.append((
            "yellow",
            "повторный блок «Будет здорово, если вы» — объедините его с предыдущим блоком дополнительных требований",
            nice["heading"],
        ))

    # Для Product & Tech нужен именно блок с примерами будущих задач, а не
    # только общий перечень обязанностей.
    direction = vac["meta"].get("направление", "").lower()
    future_examples = find_section(vac, "примеры будущих задач", "будущих задач")
    if direction in PRODUCT_TECH_DIRECTIONS and not future_examples:
        near = tasks or requirements or benefits or (sections[0] if sections else None)
        out.append((
            "yellow",
            "для Product & Tech нет блока с примерами будущих задач",
            near["heading"] if near else None,
        ))
    return out


def check_list_format(vac):
    out = []
    for s in vac["sections"]:
        items = s["items"]
        for i, it in enumerate(items):
            if re.match(r"^[А-ЯЁ]", it):
                out.append(("yellow", "пункт начинается с заглавной буквы; по гайду нужна строчная (1)", it))
            last = i == len(items) - 1
            if not last and not it.endswith(";"):
                out.append(("yellow", "пункт должен заканчиваться точкой с запятой (1)", it))
            if last and items and not it.endswith("."):
                out.append(("yellow", "последний пункт поля должен заканчиваться точкой (1)", it))
    return out


def check_requirements_legal(vac):
    out = []
    sec = find_section(vac, "жд[её]м", "ждем", "ждём", "требован")
    if sec:
        has_concrete_requirement = False
        for it in sec["items"] + sec["paragraphs"]:
            if CONCRETE_REQUIREMENT.search(it):
                has_concrete_requirement = True
        # Общие формулировки допустимы, если в блоке есть хотя бы один
        # проверяемый критерий: опыт, навык, инструмент, образование и т. п.
        if not has_concrete_requirement:
            out.append((
                "yellow",
                "в обязательных требованиях нет ни одного конкретного, проверяемого критерия",
                sec["heading"],
            ))
    return out


def check_benefits(vac):
    body = vac["body"]
    benefits = find_section(vac, "работа у нас", "условия")
    # Ведём к разделу, куда следует добавить недостающий пункт.
    quote = benefits["heading"] if benefits else None
    missing = [name for name, pat in BENEFIT_BLOCKS if not pat.search(body)]
    return [("red", f"нет обязательного блока условий: {name}", quote) for name in missing]


def check_cliches(vac):
    hits = {}
    for m in CLICHES.finditer(vac["body"]):
        term = m.group(0).lower()
        if term not in hits:
            hits[term] = [0, frag(vac["body"], m)]
        hits[term][0] += 1
    return [
        ("yellow", f"клише/канцелярит/сленг: «{term}» (2.4)", quote)
        for term, (_, quote) in hits.items()
    ]


def check_typography(vac):
    """Каждое отклонение учитывается отдельно, а не одним статусом критерия."""
    body = vac["body"]
    subs = []  # (severity, короткое описание, цитата для подсветки)

    yo = list(YO_WORDS.finditer(body))
    if yo:
        # Для этой проверки цитатой оставляем ровно проблемное слово: так ссылка
        # с text fragment подсветит «ждем», а не произвольный фрагмент рядом.
        seen_words = set()
        for match in yo:
            word = match.group(0)
            key = word.lower()
            if key in seen_words:
                continue
            seen_words.add(key)
            subs.append(("yellow", f"проверьте букву «ё»: «{key}» (2.7)", word))
    quotes = list(re.finditer(r'"[^"\n]+"', body))
    if quotes:
        for m in quotes:
            subs.append(("yellow", "компьютерные кавычки вместо «ёлочек» (2.8)", frag(body, m)))
    # Только пробелы на той же строке: иначе совпадёт markdown-маркер "- "
    # следующего пункта списка.
    dashes = list(re.finditer(r"\w[ \t]-[ \t]\w", body))
    if dashes:
        for m in dashes:
            subs.append(("yellow", "дефис вместо тире (2.10)", frag(body, m)))
    nums = list(re.finditer(r"\b\d{5,}\b", body))
    if nums:
        shown = ", ".join(m.group(0) for m in nums[:3])
        for m in nums:
            subs.append(("yellow", f"число без разбивки на разряды: {m.group(0)} (2.11)", frag(body, m)))
    avito = list(re.finditer(r"\bAvito\b(?!\s+Life)", body))
    if avito:
        for m in avito:
            subs.append(("red", "«Avito» латиницей — по-русски «Авито» (2.12)", frag(body, m)))
    hyph = list(re.finditer(r"\b(IT|HR|UX|DS|ML)\s+(сфер|направлени|инструмент|команд|специалист|систем|решени)\w*", body))
    if hyph:
        for m in hyph:
            subs.append(("yellow", f"нужен дефис: «{m.group(0)}» → «{m.group(1)}-{m.group(2)}…» (2.6)", frag(body, m)))
    years = list(re.finditer(r"\b\d+-?х\s+лет", body))
    if years:
        for m in years:
            w = m.group(0)
            subs.append(("yellow", f"«{w}» → «{w.split()[0].rstrip('х-')} лет» (2.6)", frag(body, m)))
    # «Вы» с заглавной только внутри предложения (в начале — законно)
    vy = list(re.finditer(r"[а-яё,)]\s+(Вы|Вас|Вам|Ваш\w*)\b", body))
    if vy:
        for m in vy:
            subs.append(("yellow", "«Вы/Вас/Вам» с заглавной внутри предложения (2.9)", frag(body, m)))
    brackets = list(re.finditer(r"\([^)]{2,}\)", body))
    if brackets:
        for m in brackets:
            subs.append(("yellow", "скобки в тексте: гайд советует избегать (2.4 п. 4)", frag(body, m)))
    return subs


def check_balance(vac):
    """Проверяет баланс объёма требований и преимуществ по порогу из таблицы."""
    out = []
    ben = find_section(vac, "работа у нас", "условия")
    req = find_section(vac, "ждем, что вы", "ждём, что вы", "требован")
    nice = find_section(vac, "будет здорово")
    req_words = section_word_count(req) + section_word_count(nice)
    ben_words = section_word_count(ben)
    if req_words and ben_words:
        difference = abs(req_words - ben_words) / min(req_words, ben_words)
        if difference > 0.30:
            larger = "требований" if req_words > ben_words else "преимуществ"
            percent = round(difference * 100)
            out.append((
                "yellow",
                f"дисбаланс объёма требований и преимуществ: {larger} больше на {percent}% (порог — 30%)",
                (req or ben)["heading"],
            ))
    return out


# В отчёте показываем четыре укрупнённых критерия из таблицы. Каждая
# смысловая группа считается один раз, а конкретные отклонения остаются
# списком деталей внутри неё.
def grouped_finding(severity: str, text: str, findings: list[tuple]) -> list[tuple]:
    if not findings:
        return []
    details = []
    for finding in findings:
        detail = {"text": finding[1]}
        if len(finding) > 2 and finding[2]:
            detail["quote"] = finding[2]
        details.append(detail)
    return [(severity, text, None, details)]


def check_law_compliance(vac):
    discrimination = check_discrimination(vac)
    requirements = check_requirements_legal(vac)
    legal_requirements = [f for f in requirements if f[0] == "red"]
    concrete_requirements = [f for f in requirements if f[0] == "yellow"]
    return (
        grouped_finding("red", "Дискриминационные требования", discrimination)
        + grouped_finding("red", "Некорректные обязательные требования", legal_requirements)
        + grouped_finding("yellow", "Нет конкретных требований для оценки кандидата", concrete_requirements)
    )


def check_benefits_and_advantages(vac):
    benefits = check_benefits(vac)
    balance = check_balance(vac)
    return (
        grouped_finding("red", "Не соблюдены обязательные бенефиты", benefits)
        + grouped_finding("yellow", "Дисбаланс требований и преимуществ", balance)
    )


def check_orthography_typography(vac):
    typography = check_typography(vac)
    critical = [f for f in typography if f[0] == "red"]
    noncritical = [f for f in typography if f[0] == "yellow"]
    cliches = check_cliches(vac)
    return (
        grouped_finding("red", "Критичные орфографические и типографические ошибки", critical)
        + grouped_finding("yellow", "Некритичные ошибки типографики", noncritical)
        + grouped_finding("yellow", "Клише и сленг", cliches)
    )


def check_structure_and_format(vac):
    structure = check_structure(vac)
    missing = [f for f in structure if f[0] == "red" and f[1].startswith("нет блока")]
    additional = [f for f in structure if f[0] == "red" and not f[1].startswith("нет блока")]
    nested_additional = [
        f for f in structure
        if f[0] == "yellow" and f[1].startswith((
            "повторное дополнительное требование", "повторный блок «Будет здорово"
        ))
    ]
    product_tech = [f for f in structure if f[0] == "yellow" and f not in nested_additional]
    return (
        grouped_finding("red", "Пропущены обязательные блоки", missing)
        + grouped_finding("red", "Дополнительные требования находятся в обязательном блоке", additional)
        + grouped_finding("yellow", "Повторные дополнительные требования", nested_additional)
        + grouped_finding("yellow", "Структурные замечания", product_tech)
        + grouped_finding("yellow", "Ошибки оформления списков", check_list_format(vac))
        + grouped_finding("yellow", "Замечания к названию вакансии", check_title(vac))
    )


AI_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "noncritical"]},
                    "category": {"type": "string", "enum": ["structure", "requirements", "benefits", "clarity"]},
                    "message": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["severity", "category", "message", "evidence"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["issues"],
    "additionalProperties": False,
}

# Вакансий много, поэтому не отправляем запросы к API залпом. Интервал можно
# увеличить через OPENAI_MIN_INTERVAL_SECONDS в GitHub Actions.
LAST_AI_REQUEST = 0.0


def check_meaning(vac: dict, enabled: bool) -> list[tuple]:
    """Проверка смыслового наполнения вакансии через Structured Outputs.

    Правила из гайда передаются модели вместе с текстом. Модель сообщает только
    смысловые отклонения, не дублируя типографику и детерминированные проверки.
    """
    if not enabled:
        return []
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Для проверки смыслов задайте OPENAI_API_KEY или запустите с --no-ai")
    instructions = """Ты редактор описаний вакансий Авито. Проверь только смысловое
наполнение, а не орфографию или пунктуацию. Гайд требует: обязанности должны отвечать
на вопрос «что делать» и быть конкретными; обязательные требования должны быть ясными
и проверяемыми; преимущества должны объяснять пользу кандидату; для Product & Tech
важны примеры будущих задач, решений, метрик или стейкхолдеров. Не дублируй отсутствие
заголовков и фиксированных бенефитов: это проверяет код. Верни максимум 6 уникальных
отклонений с короткой цитатой из текста. Критичной считай только ситуацию, когда
содержимое обязательного блока не даёт кандидату понять обязанности или требования;
все остальные замечания — некритичные."""
    payload = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
        "store": False,
        "input": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": json.dumps({
                "title": vac["meta"].get("title", ""),
                "direction": vac["meta"].get("направление", ""),
                "vacancy_text": vac["body"],
            }, ensure_ascii=False)},
        ],
        "text": {"format": {"type": "json_schema", "name": "vacancy_review",
                 "strict": True, "schema": AI_SCHEMA}},
    }
    global LAST_AI_REQUEST
    min_interval = float(os.environ.get("OPENAI_MIN_INTERVAL_SECONDS", "2"))
    last_error = None
    for attempt in range(6):
        wait = min_interval - (time.monotonic() - LAST_AI_REQUEST)
        if wait > 0:
            time.sleep(wait)
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                LAST_AI_REQUEST = time.monotonic()
                raw = json.loads(response.read().decode("utf-8"))
            parsed = json.loads(raw["output_text"])
            break
        except urllib.error.HTTPError as exc:
            LAST_AI_REQUEST = time.monotonic()
            last_error = exc
            if exc.code != 429 or attempt == 5:
                raise RuntimeError(f"ИИ-проверка не выполнилась: {exc}") from exc
            retry_after = exc.headers.get("Retry-After")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 5 * (attempt + 1)
            print(f"ИИ: ограничение скорости, повтор через {delay:.0f} с…", file=sys.stderr)
            time.sleep(delay)
        except (urllib.error.URLError, KeyError, ValueError) as exc:
            raise RuntimeError(f"ИИ-проверка не выполнилась: {exc}") from exc
    else:
        raise RuntimeError(f"ИИ-проверка не выполнилась: {last_error}")
    result = []
    seen = set()
    for issue in parsed.get("issues", []):
        key = (issue["category"], issue["message"], issue["evidence"])
        if key in seen:
            continue
        seen.add(key)
        severity = "red" if issue["severity"] == "critical" else "yellow"
        quote = issue["evidence"].strip()
        result.append((severity, f"ИИ: {issue['message']}", quote or None))
    return result


# ---------- утилиты ----------

def shorten(text, limit=80):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def examples(items, n=2, limit=60):
    shown = ", ".join(f"«{shorten(x, limit)}»" for x in items[:n])
    return shown + (f" и ещё {len(items) - n}" if len(items) > n else "")


def section_word_count(section: dict | None) -> int:
    """Количество слов в содержимом раздела, без его заголовка."""
    if not section:
        return 0
    text = " ".join(section["items"] + section["paragraphs"])
    return len(re.findall(r"[\wа-яё]+", text, re.I))


def context(body, m, radius=35):
    a, b = max(0, m.start() - radius), min(len(body), m.end() + radius)
    return re.sub(r"\s+", " ", body[a:b]).strip()


def frag(body, m, min_len=12):
    """Точная цитата вокруг совпадения — для подсветки через #:~:text=.

    Короткие совпадения расширяются до границ слов, чтобы фрагмент был уникальнее.
    """
    a, b = m.start(), m.end()
    while b - a < min_len and (a > 0 or b < len(body)):
        a = max(0, a - 8)
        b = min(len(body), b + 8)
    while a > 0 and not body[a - 1].isspace():
        a -= 1
    while b < len(body) and not body[b].isspace():
        b += 1
    return re.sub(r"\s+", " ", body[a:b]).strip(" \n-—•;:,.")


CRITERIA = [
    ("law", "Соблюдение законодательства", check_law_compliance),
    ("benefits", "Бенефиты и преимущества работы", check_benefits_and_advantages),
    ("typography", "Орфография/типографика", check_orthography_typography),
    ("structure", "Нарушена структура", check_structure_and_format),
]


def review(vac: dict, ai_enabled: bool) -> dict:
    result = {}
    for key, label, fn in CRITERIA:
        findings = fn(vac)
        status = "green"
        if any(f[0] == "red" for f in findings):
            status = "red"
        elif findings:
            status = "yellow"
        comments = []
        for f in findings:
            c = {"severity": f[0], "text": f[1]}
            if len(f) > 2 and f[2]:
                c["quote"] = f[2]
            if len(f) > 3 and f[3]:
                c["details"] = f[3]
            comments.append(c)
        result[key] = {"status": status, "comments": comments}
    meaning = check_meaning(vac, ai_enabled)
    if meaning:
        # ИИ-сигналы относятся к содержанию и структуре, отдельный столбец для
        # них не нужен: в таблице предусмотрены только четыре критерия.
        result["structure"]["comments"].extend(
            {"severity": f[0], "text": f[1], **({"quote": f[2]} if len(f) > 2 and f[2] else {})}
            for f in meaning
        )
        if any(f[0] == "red" for f in meaning):
            result["structure"]["status"] = "red"
        elif result["structure"]["status"] == "green":
            result["structure"]["status"] = "yellow"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-d", "--dir", default="vacancies", help="папка с md-файлами вакансий")
    parser.add_argument("-o", "--out", default="report.json", help="куда писать отчёт")
    parser.add_argument("--no-ai", action="store_true", help="не запускать смысловую проверку через OpenAI API")
    args = parser.parse_args()

    files = sorted(pathlib.Path(args.dir).glob("*.md"))
    if not files:
        print(f"✗ в {args.dir}/ нет md-файлов", file=sys.stderr)
        return 1

    # closed.json пишет fetch_vacancy.py --all: файлы, которых уже нет на сайте
    closed = set()
    closed_file = pathlib.Path("closed.json")
    if closed_file.exists():
        try:
            closed = set(json.loads(closed_file.read_text(encoding="utf-8")).get("files", []))
        except (ValueError, OSError):
            pass

    rows = []
    for path in files:
        vac = parse_md(path)
        res = review(vac, ai_enabled=not args.no_ai)
        rows.append({
            "file": vac["file"],
            "closed": vac["file"] in closed,
            "title": vac["meta"].get("title", vac["file"]),
            "url": vac["meta"].get("url", ""),
            "direction": vac["meta"].get("направление", ""),
            "team": vac["meta"].get("команда", ""),
            "location": vac["meta"].get("локация", ""),
            "published": vac["meta"].get("опубликована", ""),
            "criteria": res,
        })

    report = {
        "generated_at": datetime.datetime.now().strftime("%d.%m.%Y %H:%M"),
        "refresh_schedule": "Ежедневно в 09:00 МСК",
        "ai_enabled": not args.no_ai,
        "criteria": [{"key": k, "label": l} for k, l, _ in CRITERIA],
        "vacancies": rows,
    }
    pathlib.Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    reds = sum(1 for r in rows if any(c["status"] == "red" for c in r["criteria"].values()))
    clean_rows = sum(1 for r in rows if all(c["status"] == "green" for c in r["criteria"].values()))
    n_closed = sum(1 for r in rows if r["closed"])
    print(f"Проверено вакансий: {len(rows)}; с красными нарушениями: {reds}; полностью зелёных: {clean_rows}"
          + (f"; закрытых (уже не на сайте): {n_closed}" if n_closed else ""))
    print(f"Отчёт: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


