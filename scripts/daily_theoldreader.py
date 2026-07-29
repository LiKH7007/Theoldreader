#!/usr/bin/env python3
"""Daily The Old Reader digest for GitHub Actions.

Secrets are read only from environment variables. This script intentionally does
not print tokens, passwords, or full HTTP headers.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
import smtplib
import ssl
import sys
import textwrap
import urllib.parse
from email.message import EmailMessage
from email.utils import formatdate
from typing import Any

import requests
from zoneinfo import ZoneInfo


API = "https://theoldreader.com/reader/api/0"
DEFAULT_STREAM = "user/-/state/com.google/reading-list"
USER_AGENT = "github-actions-theoldreader-radar/1.0"
TAG_RE = re.compile(r"<[^>]+>")
DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
ISSUE_RE = re.compile(r"issue information|\(adv\. mater\.\s*\d+/\d{4}\)", re.I)


def getenv(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def require_env(name: str) -> str:
    value = getenv(name)
    if not value:
        raise SystemExit(f"Missing required environment variable or GitHub Secret: {name}")
    return value


def as_int(name: str, default: int) -> int:
    value = getenv(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {value!r}") from exc


def strip_html(text: str) -> str:
    text = TAG_RE.sub(" ", text or "")
    text = html.unescape(text)
    return " ".join(text.split())


def first_doi(*texts: str) -> str:
    for text in texts:
        match = DOI_RE.search(text or "")
        if match:
            return match.group(1).rstrip(".,);")
    return ""


def item_url(item: dict[str, Any]) -> str:
    for alt in item.get("alternate", []) or []:
        href = alt.get("href")
        if href:
            return href
    canonical = item.get("canonical") or []
    if canonical and canonical[0].get("href"):
        return canonical[0]["href"]
    return ""


def item_date(item: dict[str, Any]) -> str:
    raw = item.get("crawlTimeMsec") or item.get("published") or item.get("updated")
    if raw is None:
        return ""
    timestamp = int(raw)
    if timestamp > 10_000_000_000:
        timestamp //= 1000
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()


def origin_title(item: dict[str, Any]) -> str:
    origin = item.get("origin") or {}
    return origin.get("title") or item.get("sourceTitle") or ""


def fetch_unread_items(token: str) -> list[dict[str, Any]]:
    limit = as_int("TOR_LIMIT", 100)
    params = {
        "output": "json",
        "s": getenv("TOR_STREAM", DEFAULT_STREAM),
        "n": str(limit),
        "xt": "user/-/state/com.google/read",
    }
    url = f"{API}/stream/contents?{urllib.parse.urlencode(params)}"
    response = requests.get(
        url,
        headers={
            "Authorization": f"GoogleLogin auth={token}",
            "User-Agent": USER_AGENT,
        },
        timeout=45,
    )
    response.raise_for_status()
    return response.json().get("items", [])


def normalize_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    max_items = as_int("TOR_MAX_ITEMS", 30)

    for item in items:
        title = strip_html(item.get("title", ""))
        if not title or ISSUE_RE.search(title):
            continue

        summary = strip_html((item.get("summary") or {}).get("content", "") or (item.get("content") or {}).get("content", ""))
        url = item_url(item)
        doi = first_doi(title, summary, url)
        key = (doi.lower(), title.lower())
        if key in seen:
            continue
        seen.add(key)

        rows.append(
            {
                "date": item_date(item),
                "feed": origin_title(item),
                "title": title,
                "author": strip_html(item.get("author", "")),
                "doi": doi,
                "url": url,
                "summary": summary[:1600],
            }
        )
        if len(rows) >= max_items:
            break

    return rows


def fallback_digest(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "今天 The Old Reader 没有抓到新的未读条目。"

    lines = ["# The Old Reader Daily Digest", ""]
    for index, row in enumerate(rows, 1):
        lines.append(f"{index}. {row['title']}")
        if row["feed"]:
            lines.append(f"   - 来源: {row['feed']}")
        if row["doi"]:
            lines.append(f"   - DOI: {row['doi']}")
        if row["url"]:
            lines.append(f"   - 链接: {row['url']}")
        if row["summary"]:
            lines.append(f"   - 摘要: {row['summary'][:300]}")
        lines.append("")
    return "\n".join(lines).strip()


def parse_openai_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()

    chunks: list[str] = []
    for output in data.get("output", []) or []:
        for content in output.get("content", []) or []:
            if isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "\n".join(chunks).strip()


def ai_digest(rows: list[dict[str, str]]) -> str:
    api_key = getenv("OPENAI_API_KEY")
    if not api_key or not rows:
        return fallback_digest(rows)

    model = getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = textwrap.dedent(
        """
        请把下面 The Old Reader 抓到的论文/资讯条目整理成中文每日文献雷达。
        要求：
        1. 按优先级分成 [必读]、[值得下载]、[扫读即可]、[跳过]。
        2. 每条推荐内容说明材料/体系、核心现象或机制、为什么值得看、下一步建议。
        3. 如果摘要信息不足，请明确写“摘要不足，需要打开网页复核”。
        4. 输出适合直接作为邮件正文的 Markdown。

        条目 JSON：
        """
    ).strip()
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "你是材料科学文献雷达助手，偏好简洁、准确、可行动的中文摘要。",
            },
            {
                "role": "user",
                "content": f"{prompt}\n{json.dumps(rows, ensure_ascii=False, indent=2)}",
            },
        ],
        "temperature": 0.2,
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        text = parse_openai_text(response.json())
        return text or fallback_digest(rows)
    except requests.RequestException as exc:
        print(f"OpenAI summarization failed; sending fallback digest instead: {exc}", file=sys.stderr)
        return fallback_digest(rows)


def send_email(subject: str, body: str) -> None:
    host = require_env("SMTP_HOST")
    port = int(getenv("SMTP_PORT", "465"))
    username = require_env("SMTP_USER")
    password = require_env("SMTP_PASSWORD")
    mail_from = require_env("MAIL_FROM")
    mail_to = require_env("MAIL_TO")
    use_ssl = getenv("SMTP_SSL", "true").lower() not in {"0", "false", "no"}

    message = EmailMessage()
    message["From"] = mail_from
    message["To"] = mail_to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    message.set_content(body)

    if use_ssl:
        with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=45) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=45) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(username, password)
            smtp.send_message(message)


def main() -> int:
    token = require_env("TOR_TOKEN")
    today = dt.datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    items = fetch_unread_items(token)
    rows = normalize_items(items)
    body = ai_digest(rows)
    subject = f"The Old Reader Daily Radar - {today} - {len(rows)} items"
    send_email(subject, body)
    print(f"Sent digest with {len(rows)} normalized items.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(f"HTTP request failed with status {status}.", file=sys.stderr)
        raise
