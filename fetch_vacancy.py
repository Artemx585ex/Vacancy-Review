#!/usr/bin/env python3
"""Выкачивает вакансии с career.avito.com и сохраняет их в markdown-файлы.

Использование:
    python3 fetch_vacancy.py URL [URL ...] [-o ПАПКА]      # конкретные вакансии
    python3 fetch_vacancy.py --all [-o ПАПКА]              # все вакансии сайта
    python3 fetch_vacancy.py https://career.avito.com/vacancies/  # то же, что --all

Список всех вакансий берётся из sitemap сайта (sitemap-iblock-2.xml).
Уже скачанные вакансии пропускаются, --force перекачивает заново.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import html
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

BASE = "https://career.avito.com"
SITEMAP_URL = f"{BASE}/sitemap-iblock-2.xml"
VACANCY_URL_RE = re.compile(r"https?://career\.avito\.com/vacancies/[\w-]+/(\d+)/?$")
DEFAULT_JOBS = 15  # параллельных загрузок
RETRIES = 3       # попыток на страницу при сетевых сбоях и 429/5xx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def fetch(url: str) -> str:
    last_exc: Exception = RuntimeError("fetch не выполнялся")
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504):
                raise  # 404 и прочие 4xx повторами не лечатся
            last_exc = exc
        except OSError as exc:  # таймауты, обрывы соединения, DNS
            last_exc = exc
        if attempt < RETRIES:
            time.sleep(2 * attempt)
    raise last_exc


def all_vacancy_urls() -> list[str]:
    """Все ссылки на вакансии из sitemap карьерного сайта."""
    sitemap = fetch(SITEMAP_URL)
    urls = re.findall(r"<loc>(https://career\.avito\.com/vacancies/[\w-]+/\d+/)</loc>", sitemap)
    return sorted(set(urls))


def job_posting(raw: str) -> dict:
    """JSON-LD JobPosting со страницы (метаданные вакансии)."""
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', raw, re.S
    ):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if data.get("@type") == "JobPosting":
            return data
    return {}


def page_info(raw: str) -> dict:
    """Пары «Команда → Товары», «Локация → Москва, гибрид» из шапки вакансии."""
    info = {}
    for m in re.finditer(
        r'page-info__link-label">([^<]+)</span>\s*'
        r'<(?:a|span)[^>]*page-info__link-text[^>]*>([^<]+)<',
        raw,
    ):
        info[clean(m.group(1))] = clean(m.group(2))
    return info


def clean(text: str) -> str:
    text = html.unescape(text).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def sections_to_md(raw: str) -> str:
    """Секции описания вакансии → markdown (заголовки и списки)."""
    parts = []
    for m in re.finditer(
        r'<section class="vacancies-detail__description">(.*?)</section>', raw, re.S
    ):
        block = m.group(1)
        out = []
        for tag, inner in re.findall(r"<(h2|li|p)[^>]*>(.*?)</\1>", block, re.S):
            text = clean(re.sub(r"<[^>]+>", " ", inner))
            if not text:
                continue
            if tag == "h2":
                out.append(f"\n## {text}\n")
            elif tag == "li":
                out.append(f"- {text}")
            else:
                out.append(f"\n{text}\n")
        if out:
            parts.append("\n".join(out))
    return "\n".join(parts).strip()


def slugify(title: str) -> str:
    slug = re.sub(r"[^\w-]+", "-", title.lower(), flags=re.U).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def vacancy_id(url: str) -> str:
    m = VACANCY_URL_RE.match(url)
    return m.group(1) if m else "unknown"


def already_saved(url: str, out_dir: pathlib.Path) -> pathlib.Path | None:
    hits = list(out_dir.glob(f"{vacancy_id(url)}-*.md"))
    return hits[0] if hits else None


def save_vacancy(url: str, out_dir: pathlib.Path) -> pathlib.Path:
    raw = fetch(url)
    posting = job_posting(raw)
    info = page_info(raw)
    body = sections_to_md(raw)
    if not body:
        raise ValueError("не нашёл описание вакансии на странице (нет секций)")

    title = clean(posting.get("title", "")) or "вакансия"

    front = {
        "title": title,
        "url": url,
        "id": vacancy_id(url),
        "направление": clean(posting.get("identifier", {}).get("name", "")),
        "команда": info.get("Команда", ""),
        "локация": info.get("Локация", "")
        or clean(posting.get("jobLocation", {}).get("address", {}).get("addressLocality", "")),
        "опубликована": posting.get("datePosted", "")[:10],
    }
    fm = "\n".join(f"{k}: {v}" for k, v in front.items() if v)

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{vacancy_id(url)}-{slugify(title)}.md"
    path.write_text(f"---\n{fm}\n---\n\n# {title}\n\n{body}\n", encoding="utf-8")
    return path


def collect_urls(args: argparse.Namespace) -> "tuple[list[str], bool]":
    """Разворачивает аргументы в список ссылок; второй элемент — был ли полный листинг."""
    urls: list[str] = []
    listing_requested = args.all
    for url in args.urls:
        if VACANCY_URL_RE.match(url):
            urls.append(url)
        elif re.match(r"https?://career\.avito\.com/vacancies/?([\w-]+/?)?$", url):
            listing_requested = True
        else:
            print(f"✗ не похоже на вакансию career.avito.com, пропускаю: {url}", file=sys.stderr)
    if listing_requested:
        urls.extend(all_vacancy_urls())
    # дедупликация с сохранением порядка
    return list(dict.fromkeys(urls)), listing_requested


def mark_closed(urls: "list[str]", out_dir: pathlib.Path) -> None:
    """Сверяет локальные md-файлы с полным списком сайта и пишет closed.json.

    Закрытые вакансии не удаляются — отчёт помечает их «не на сайте»,
    а удалить их можно кнопкой в интерфейсе (через serve.py).
    """
    active = {vacancy_id(u) for u in urls}
    closed = sorted(p.name for p in out_dir.glob("*.md")
                    if p.name.split("-", 1)[0] not in active)
    pathlib.Path("closed.json").write_text(
        json.dumps({"files": closed}, ensure_ascii=False, indent=1), encoding="utf-8")
    if closed:
        print(f"Закрытых вакансий (файл есть, на сайте уже нет): {len(closed)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("urls", nargs="*", help="ссылки на вакансии career.avito.com")
    parser.add_argument("--all", action="store_true", help="выкачать все вакансии сайта из sitemap")
    parser.add_argument("--force", action="store_true", help="перекачивать уже сохранённые вакансии")
    parser.add_argument(
        "-o", "--out-dir", default="vacancies", help="папка для md-файлов (по умолчанию vacancies/)"
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=DEFAULT_JOBS,
        help=f"число параллельных загрузок (по умолчанию {DEFAULT_JOBS})"
    )
    args = parser.parse_args()
    if not args.urls and not args.all:
        parser.error("укажите ссылки или --all")

    out_dir = pathlib.Path(args.out_dir)
    urls, listing = collect_urls(args)
    if not urls:
        print("✗ не нашлось ни одной ссылки на вакансии", file=sys.stderr)
        return 1

    todo = urls if args.force else [u for u in urls if not already_saved(u, out_dir)]
    skipped = len(urls) - len(todo)
    print(f"Вакансий на сайте: {len(urls)}; уже скачаны: {skipped}, к скачиванию: {len(todo)}")
    if listing:  # полный список с сайта — можно понять, какие локальные файлы закрыты
        mark_closed(urls, out_dir)
    if not todo:
        print("\nГотово: всё уже скачано, нового нет")
        return 0

    saved = failed = done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futures = {pool.submit(save_vacancy, url, out_dir): url for url in todo}
        for fut in concurrent.futures.as_completed(futures):
            url = futures[fut]
            done += 1
            try:
                path = fut.result()
                print(f"[{done}/{len(todo)}] ✓ {url} → {path}")
                saved += 1
            except Exception as exc:
                print(f"[{done}/{len(todo)}] ✗ {url}: {exc}", file=sys.stderr)
                failed += 1

    print(f"\nГотово: скачано {saved}, пропущено {skipped}, ошибок {failed}")
    # Одна временно недоступная вакансия не должна останавливать весь отчёт:
    # при --force для неё остаётся предыдущая сохранённая версия. Но если
    # не скачалось вообще ничего, завершаем запуск с ошибкой.
    if failed and saved:
        print("⚠️ Часть вакансий временно недоступна: использованы последние сохранённые данные.")
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
