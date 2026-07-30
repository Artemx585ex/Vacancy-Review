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
import pathlib
import re
import sys

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

PERSONAL_QUALITIES = re.compile(
    r"проактивн|стрессоустойчив|аналитическ\w+\s+склад|системн\w+\s+мышлени"
    r"|гибкость|адаптир\w+ся|ориентирован\w*\s+на\s+результат|коммуникабельн"
    r"|инициативн|командн\w+\s+игрок|многозадачн|внимательн\w+\s+к\s+деталям"
    r"|лидерск\w+\s+качеств|энергичн|амбициозн|гореть\s+идеей|горите\s+идеей",
    re.I,
)

CLICHES = re.compile(
    r"\bданн(?:ый|ая|ое|ого|ой|ую|ом)\b|молод(?:ой|ым)\s+и\s+дружн|дружн\w+\s+коллектив"
    r"|печеньк|гор(?:еть|ите|ящих)\s+идее|доставк\w+\s+проектов|чай,\s*кофе"
    r"|команд\w+\s+мечты|динамично\s+развива|пенетраци|селлер",
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

def check_title(vac):
    out = []
    title = vac["meta"].get("title", "")
    if re.search(r"[()]", title):
        out.append(("red", f"скобки в названии: «{title}» — гайд запрещает скобки (2.4 п. 4)", title))
    latin = re.findall(r"[A-Za-z][A-Za-z&-]+", title)
    role_words = {"manager", "senior", "junior", "lead", "head", "developer", "engineer",
                  "designer", "analyst", "director", "specialist", "product", "project", "owner"}
    bad = [w for w in latin if w.lower() in role_words]
    if bad:
        out.append(("red", f"должность латиницей в названии: {', '.join(bad)} — название пишется по-русски (2.1)", title))
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
            sev = "red" if what in ("возраст", "пол") else "yellow"
            out.append((sev, f"возможная дискриминация ({what}): «…{context(body, m)}…» — ст. 3 и 64 ТК РФ",
                        frag(body, m)))
    return out


def check_structure(vac):
    out = []
    if not find_section(vac, "задачи вас ждут", "будущих задач", "предстоит заниматься"):
        out.append(("red", "нет блока задач («Какие задачи вас ждут» или «Примеры будущих задач»)"))
    if not find_section(vac, "ждем, что вы", "ждём, что вы", "требован"):
        out.append(("red", "нет блока требований («Мы ждём, что вы»)"))
    if not find_section(vac, "работа у нас", "условия"):
        out.append(("red", "нет блока условий («Работа у нас — это»)"))
    return out


def check_list_format(vac):
    caps, semis, dots = [], [], []
    for s in vac["sections"]:
        items = s["items"]
        for i, it in enumerate(items):
            if re.match(r"^[А-ЯЁ]", it):
                caps.append(it)
            last = i == len(items) - 1
            if not last and not it.endswith(";"):
                semis.append(it)
            if last and items and not it.endswith("."):
                dots.append(it)
    out = []
    if caps:
        out.append(("red", f"пункты с заглавной буквы ({len(caps)} шт., должны начинаться со строчной): {examples(caps)}",
                    caps[0]))
    if semis:
        out.append(("yellow", f"пункты без «;» на конце ({len(semis)} шт.): {examples(semis)}", semis[0]))
    if dots:
        out.append(("yellow", f"последний пункт поля должен заканчиваться точкой ({len(dots)} шт.): {examples(dots)}",
                    dots[0]))
    return out


def check_requirements_legal(vac):
    out = []
    sec = find_section(vac, "жд[её]м", "ждем", "ждём", "требован")
    if sec:
        for it in sec["items"]:
            m = PERSONAL_QUALITIES.search(it)
            if m:
                out.append(("yellow", f"личное качество в требованиях: «{shorten(it)}» — по нему нельзя юридически отказать; перенести в «Будет здорово, если вы» или убрать",
                            it))
    return out


def check_benefits(vac):
    body = vac["body"]
    missing = [name for name, pat in BENEFIT_BLOCKS if not pat.search(body)]
    if not missing:
        return []
    sev = "red" if len(missing) >= 3 else "yellow"
    listing = "; ".join(missing)
    return [(sev, f"не хватает {len(missing)} из 5 обязательных блоков условий: {listing}")]


def check_cliches(vac):
    hits = {}
    for m in CLICHES.finditer(vac["body"]):
        term = m.group(0).lower()
        if term not in hits:
            hits[term] = [0, frag(vac["body"], m)]
        hits[term][0] += 1
    return [
        ("yellow", f"клише/канцелярит/сленг: «{term}»{f' — {n} раза' if n > 1 else ''} (2.4)", quote)
        for term, (n, quote) in hits.items()
    ]


def check_typography(vac):
    """Вся типографика вакансии (кавычки, тире, «ё», скобки и т.д.) — одним пунктом."""
    body = vac["body"]
    subs = []  # (severity, короткое описание, цитата для подсветки)

    yo = list(YO_WORDS.finditer(body))
    if yo:
        words = sorted({m.group(0).lower() for m in yo})
        subs.append(("yellow", f"буква «ё»: {', '.join(f'«{w}»' for w in words)} (2.7)", frag(body, yo[0])))
    quotes = list(re.finditer(r'"[^"\n]+"', body))
    if quotes:
        subs.append(("red", f"компьютерные кавычки вместо «ёлочек» ({len(quotes)} шт.) (2.8)", frag(body, quotes[0])))
    dashes = list(re.finditer(r"\w\s-\s\w", body))
    if dashes:
        subs.append(("red", f"дефис вместо тире ({len(dashes)} шт.) (2.10)", frag(body, dashes[0])))
    nums = list(re.finditer(r"\b\d{5,}\b", body))
    if nums:
        shown = ", ".join(m.group(0) for m in nums[:3])
        subs.append(("yellow", f"числа без разбивки на разряды: {shown} (2.11)", frag(body, nums[0])))
    avito = list(re.finditer(r"\bAvito\b(?!\s+Life)", body))
    if avito:
        subs.append(("red", "«Avito» латиницей — по-русски «Авито» (2.12)", frag(body, avito[0])))
    hyph = list(re.finditer(r"\b(IT|HR|UX|DS|ML)\s+(сфер|направлени|инструмент|команд|специалист|систем|решени)\w*", body))
    if hyph:
        m = hyph[0]
        subs.append(("red", f"нужен дефис: «{m.group(0)}» → «{m.group(1)}-{m.group(2)}…» (2.6)", frag(body, m)))
    years = list(re.finditer(r"\b\d+-?х\s+лет", body))
    if years:
        w = years[0].group(0)
        subs.append(("red", f"«{w}» → «{w.split()[0].rstrip('х-')} лет» (2.6)", frag(body, years[0])))
    # «Вы» с заглавной только внутри предложения (в начале — законно)
    vy = list(re.finditer(r"[а-яё,)]\s+(Вы|Вас|Вам|Ваш\w*)\b", body))
    if vy:
        subs.append(("yellow", f"«Вы/Вас/Вам» с заглавной внутри предложения ({len(vy)} шт.) (2.9)", frag(body, vy[0])))
    brackets = list(re.finditer(r"\([^)]{2,}\)", body))
    if brackets:
        subs.append(("yellow", f"скобки в тексте ({len(brackets)} шт., гайд советует избегать) (2.4 п. 4)",
                     frag(body, brackets[0])))

    if not subs:
        return []
    sev = "red" if any(s[0] == "red" for s in subs) else "yellow"
    text = "типографика: " + "; ".join(s[1] for s in subs)
    quote = next((s[2] for s in subs if s[0] == "red"), subs[0][2])
    return [(sev, text, quote)]


def check_balance(vac):
    """Требований не должно быть больше, чем преимуществ работы: это отпугивает кандидатов."""
    out = []
    ben = find_section(vac, "работа у нас", "условия")
    req = find_section(vac, "ждем, что вы", "ждём, что вы", "требован")
    nice = find_section(vac, "будет здорово")
    n_ben = len(ben["items"]) if ben else 0
    n_req = (len(req["items"]) if req else 0) + (len(nice["items"]) if nice else 0)
    if ben and 0 < n_ben < 5:
        out.append(("yellow", f"в блоке «{ben['heading']}» только {n_ben} пункт(а) — похоже, не хватает части условий и преимуществ работы"))
    if n_req and n_ben and n_req > n_ben:
        out.append(("yellow", f"требований больше, чем преимуществ работы ({n_req} против {n_ben}) — это отпугивает кандидатов; добавьте пунктов в «{ben['heading']}» или сократите требования"))
    return out


# ---------- утилиты ----------

def shorten(text, limit=80):
    return text if len(text) <= limit else text[: limit - 1] + "…"


def examples(items, n=2, limit=60):
    shown = ", ".join(f"«{shorten(x, limit)}»" for x in items[:n])
    return shown + (f" и ещё {len(items) - n}" if len(items) > n else "")


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
    ("title", "Название", check_title),
    ("discrimination", "Дискриминация", check_discrimination),
    ("structure", "Структура блоков", check_structure),
    ("benefits", "5 блоков условий", check_benefits),
    ("requirements", "Юр. отказные требования", check_requirements_legal),
    ("lists", "Оформление списков", check_list_format),
    ("cliches", "Клише и сленг", check_cliches),
    ("typography", "Типографика", check_typography),
    ("balance", "Требования vs преимущества", check_balance),
]


def review(vac: dict) -> dict:
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
            comments.append(c)
        result[key] = {"status": status, "comments": comments}
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-d", "--dir", default="vacancies", help="папка с md-файлами вакансий")
    parser.add_argument("-o", "--out", default="report.json", help="куда писать отчёт")
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
        res = review(vac)
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
