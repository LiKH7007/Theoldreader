#!/usr/bin/env python3
"""Daily The Old Reader digest for GitHub Actions.

Secrets are read only from environment variables. This script intentionally does
not print tokens, passwords, SecretId, SecretKey, OpenAI keys, or full HTTP
headers.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import html
import json
import os
import re
import smtplib
import ssl
import sys
import textwrap
import time
import urllib.parse
from email.message import EmailMessage
from email.utils import formatdate
from typing import Any

import requests
from zoneinfo import ZoneInfo


API = "https://theoldreader.com/reader/api/0"
DEFAULT_READING_LIST = "user/-/state/com.google/reading-list"
USER_AGENT = "github-actions-theoldreader-radar/2.0"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
TAG_RE = re.compile(r"<[^>]+>")
DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
ISSUE_RE = re.compile(r"issue information|\(adv\. mater\.\s*\d+/\d{4}\)", re.I)
ABSTRACT_RE = re.compile(
    r"(?:abstract|summary)\s*[:\n]\s*(.{120,2500}?)(?:\n\s*(?:introduction|keywords|references|全文|图文)|$)",
    re.I | re.S,
)
META_RE = re.compile(
    r'<meta\s+(?:name|property)=["\'](?:description|og:description|twitter:description|citation_abstract|dc.description)["\']\s+content=["\'](.*?)["\']',
    re.I | re.S,
)


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


def as_bool(name: str, default: bool) -> bool:
    value = getenv(name)
    if not value:
        return default
    return value.lower() not in {"0", "false", "no", "off"}


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


def parse_timestamp(item: dict[str, Any]) -> int | None:
    raw = item.get("crawlTimeMsec") or item.get("published") or item.get("updated")
    if raw is None:
        return None
    timestamp = int(raw)
    if timestamp > 10_000_000_000:
        timestamp //= 1000
    return timestamp


def item_date(item: dict[str, Any]) -> str:
    timestamp = parse_timestamp(item)
    if timestamp is None:
        return ""
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).astimezone(LOCAL_TZ).date().isoformat()


def item_url(item: dict[str, Any]) -> str:
    for alt in item.get("alternate", []) or []:
        href = alt.get("href")
        if href:
            return href
    canonical = item.get("canonical") or []
    if canonical and canonical[0].get("href"):
        return canonical[0]["href"]
    return ""


def origin_title(item: dict[str, Any]) -> str:
    origin = item.get("origin") or {}
    return origin.get("title") or item.get("sourceTitle") or ""


def api_get(token: str, path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    response = requests.get(
        url,
        headers={
            "Authorization": f"GoogleLogin auth={token}",
            "User-Agent": USER_AGENT,
        },
        timeout=45,
    )
    response.raise_for_status()
    return response.json()


def fetch_subscriptions(token: str) -> list[dict[str, Any]]:
    data = api_get(token, "subscription/list", {"output": "json"})
    return data.get("subscriptions", [])


def fetch_stream_items(
    token: str,
    stream_id: str,
    *,
    unread_only: bool,
    since_ts: int | None = None,
) -> list[dict[str, Any]]:
    """Fetch a stream, walking continuation pages until old items are reached.

    There is no semantic item cap by default. API calls are still paged because
    The Old Reader returns stream contents in pages.
    """

    page_size = min(max(as_int("TOR_API_PAGE_SIZE", 100), 1), 1000)
    max_pages = as_int("TOR_MAX_PAGES_PER_FEED", 0)
    items: list[dict[str, Any]] = []
    continuation = ""
    pages = 0

    while True:
        pages += 1
        params = {"output": "json", "s": stream_id, "n": str(page_size)}
        if unread_only:
            params["xt"] = "user/-/state/com.google/read"
        if continuation:
            params["c"] = continuation

        data = api_get(token, "stream/contents", params)
        batch = data.get("items", [])
        if not batch:
            break

        reached_old_item = False
        for item in batch:
            timestamp = parse_timestamp(item)
            if since_ts is not None and timestamp is not None and timestamp < since_ts:
                reached_old_item = True
                continue
            items.append(item)

        continuation = data.get("continuation", "")
        if not continuation or reached_old_item:
            break
        if max_pages > 0 and pages >= max_pages:
            print(
                f"Reached TOR_MAX_PAGES_PER_FEED={max_pages} for stream {stream_id}; "
                "increase it if a very active feed is truncated.",
                file=sys.stderr,
            )
            break

    return items


def fetch_unread_items(token: str) -> list[dict[str, Any]]:
    return fetch_stream_items(
        token,
        getenv("TOR_STREAM", DEFAULT_READING_LIST),
        unread_only=True,
        since_ts=None,
    )


def fetch_subscription_latest_items(token: str) -> list[dict[str, Any]]:
    """Fetch recent items from every subscription in The Old Reader.

    Defaults to all subscriptions and all items in the recent lookback window.
    It does not restrict journals or item count.
    """

    lookback_hours = as_int("TOR_LOOKBACK_HOURS", 24)
    since_ts = int((dt.datetime.now(LOCAL_TZ) - dt.timedelta(hours=lookback_hours)).timestamp())
    unread_only = as_bool("TOR_ONLY_UNREAD", False)
    subscriptions = fetch_subscriptions(token)
    print(
        f"Subscription latest mode: subscriptions={len(subscriptions)}, "
        f"lookback_hours={lookback_hours}, unread_only={unread_only}"
    )

    all_items: list[dict[str, Any]] = []
    for sub in subscriptions:
        stream_id = sub.get("id")
        if not stream_id:
            continue
        try:
            stream_items = fetch_stream_items(token, stream_id, unread_only=unread_only, since_ts=since_ts)
        except requests.RequestException as exc:
            print(f"Skipping one subscription after fetch failure: {exc}", file=sys.stderr)
            continue
        for item in stream_items:
            item.setdefault("origin", {})
            if not item["origin"].get("title"):
                item["origin"]["title"] = sub.get("title", "")
            all_items.append(item)

    return all_items


def fetch_items(token: str) -> list[dict[str, Any]]:
    source_mode = getenv("TOR_SOURCE_MODE", "subscriptions_latest").lower()
    if source_mode in {"subscriptions_latest", "subscriptions-latest", "latest"}:
        return fetch_subscription_latest_items(token)
    if source_mode in {"unread", "reading_list", "reading-list"}:
        return fetch_unread_items(token)
    print(f"Unknown TOR_SOURCE_MODE={source_mode!r}; using subscriptions_latest.", file=sys.stderr)
    return fetch_subscription_latest_items(token)


def should_enrich_summary(summary: str) -> bool:
    min_chars = as_int("TOR_MIN_SUMMARY_CHARS", 120)
    return as_bool("TOR_FETCH_ARTICLE_PAGE", True) and len(summary or "") < min_chars


def extract_web_summary(raw_html: str) -> str:
    for match in META_RE.finditer(raw_html or ""):
        text = strip_html(match.group(1))
        if len(text) >= 80:
            return text[:1800]
    text = strip_html(raw_html)
    match = ABSTRACT_RE.search(text)
    if match:
        return strip_html(match.group(1))[:1800]
    return ""


def fetch_article_summary(url: str) -> str:
    if not url or not url.startswith(("http://", "https://")):
        return ""
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        return ""
    return extract_web_summary(response.text)


def normalize_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    max_items = as_int("TOR_MAX_ITEMS", 0)

    newest_first = sorted(items, key=lambda item: parse_timestamp(item) or 0, reverse=True)
    for item in newest_first:
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

        summary_source = "rss"
        if should_enrich_summary(summary):
            web_summary = fetch_article_summary(url)
            if len(web_summary) > len(summary):
                summary = web_summary
                summary_source = "article_page"
            else:
                summary_source = "rss_insufficient"

        rows.append(
            {
                "date": item_date(item),
                "feed": origin_title(item),
                "title": title,
                "author": strip_html(item.get("author", "")),
                "doi": doi,
                "url": url,
                "summary": summary[:1800],
                "summary_source": summary_source,
            }
        )
        if max_items > 0 and len(rows) >= max_items:
            break

    return rows


def fallback_digest(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "今天 The Old Reader 的订阅源在设定时间窗口内没有抓到新条目。"

    lines = ["# The Old Reader Daily Radar", "", "模式：订阅源最新更新；未使用 AI 摘要。", ""]
    for index, row in enumerate(rows, 1):
        lines.append(f"{index}. {row['title']}")
        if row["feed"]:
            lines.append(f"   - 订阅源: {row['feed']}")
        if row["date"]:
            lines.append(f"   - 日期: {row['date']}")
        if row["doi"]:
            lines.append(f"   - DOI: {row['doi']}")
        if row["url"]:
            lines.append(f"   - 链接: {row['url']}")
        if row["summary"]:
            lines.append(f"   - 摘要: {row['summary'][:500]}")
        else:
            lines.append("   - 摘要: 摘要不足，需要打开网页复核。")
        lines.append("")
    return "\n".join(lines).strip()


def tencent_secret(name: str) -> str:
    return getenv(name) or getenv(f"TENCENTCLOUD_{name.removeprefix('TENCENT_')}")


def has_tencent_credentials() -> bool:
    return bool(tencent_secret("TENCENT_SECRET_ID") and tencent_secret("TENCENT_SECRET_KEY"))


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hmac_sha256(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


def translate_with_tencent(text: str, source: str = "auto", target: str = "zh") -> str:
    text = " ".join((text or "").split())
    if not text:
        return ""

    secret_id = tencent_secret("TENCENT_SECRET_ID")
    secret_key = tencent_secret("TENCENT_SECRET_KEY")
    service = "tmt"
    host = getenv("TENCENT_TMT_ENDPOINT", "tmt.tencentcloudapi.com")
    region = getenv("TENCENT_REGION", "ap-beijing")
    action = "TextTranslate"
    version = "2018-03-21"
    algorithm = "TC3-HMAC-SHA256"
    timestamp = int(time.time())
    date = dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%Y-%m-%d")

    payload = json.dumps(
        {
            "SourceText": text[:1800],
            "Source": source,
            "Target": target,
            "ProjectId": 0,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    canonical_headers = (
        "content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    canonical_request = "\n".join(
        [
            "POST",
            "/",
            "",
            canonical_headers,
            signed_headers,
            sha256_hex(payload),
        ]
    )
    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = "\n".join(
        [
            algorithm,
            str(timestamp),
            credential_scope,
            sha256_hex(canonical_request),
        ]
    )
    secret_date = hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = hmac_sha256(secret_date, service)
    secret_signing = hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    response = requests.post(
        f"https://{host}",
        headers={
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-TC-Action": action,
            "X-TC-Version": version,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": region,
        },
        data=payload.encode("utf-8"),
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    result = data.get("Response", {})
    if result.get("Error"):
        error = result["Error"]
        raise RuntimeError(f"{error.get('Code')}: {error.get('Message')}")
    return result.get("TargetText", "")


def tencent_digest(rows: list[dict[str, str]]) -> str:
    if not rows:
        return fallback_digest(rows)
    if not has_tencent_credentials():
        return fallback_digest(rows)

    try:
        target = getenv("TENCENT_TARGET", "zh")
        lines = ["# The Old Reader Daily Radar", "", "模式：订阅源最新更新", "翻译服务：腾讯云机器翻译", ""]
        for index, row in enumerate(rows, 1):
            title_zh = translate_with_tencent(row["title"], target=target)
            time.sleep(0.25)
            summary_zh = ""
            if row["summary"]:
                summary_zh = translate_with_tencent(row["summary"][:1000], target=target)
                time.sleep(0.25)

            lines.append(f"{index}. {title_zh or row['title']}")
            lines.append(f"   - 原题: {row['title']}")
            if row["feed"]:
                lines.append(f"   - 订阅源: {row['feed']}")
            if row["date"]:
                lines.append(f"   - 日期: {row['date']}")
            if row["doi"]:
                lines.append(f"   - DOI: {row['doi']}")
            if row["url"]:
                lines.append(f"   - 链接: {row['url']}")
            if summary_zh:
                lines.append(f"   - 摘要: {summary_zh}")
            else:
                lines.append("   - 摘要: 摘要不足，需要打开网页复核。")
            lines.append("")
        return "\n".join(lines).strip()
    except Exception as exc:
        print(f"Tencent translation failed; sending fallback digest instead: {exc}", file=sys.stderr)
        return fallback_digest(rows)


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
        return tencent_digest(rows) if has_tencent_credentials() else fallback_digest(rows)

    model = getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = textwrap.dedent(
        """
        请把下面 The Old Reader 订阅源最新更新条目整理成中文每日文献雷达。

        核心规则：
        1. 只总结标题和摘要/网页摘要中的信息，不读取 PDF，也不要虚构摘要中没有的结论。
        2. 按 [必读]、[值得下载]、[扫读即可]、[跳过] 分组。
        3. 每条 [必读] 或 [值得下载] 必须包含：
           - 材料/体系
           - 新现象/机制/方法
           - 为什么重要
           - 证据来源：RSS 摘要、网页摘要、题名推断、摘要不足
           - 建议动作
        4. 如果 summary_source 是 rss_insufficient，必须写“摘要不足，需要打开网页复核”，并且不要列为 [必读]。
        5. 如果是生活、新闻、非学术、纯广告或无法判断的条目，放入 [跳过]。
        6. 输出适合直接作为邮件正文的 Markdown。

        条目 JSON：
        """
    ).strip()
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "你是材料科学文献雷达助手，偏好准确、具体、可行动的中文摘要。",
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
        print(f"OpenAI summarization failed; trying Tencent translation instead: {exc}", file=sys.stderr)
        return tencent_digest(rows) if has_tencent_credentials() else fallback_digest(rows)


def make_digest(rows: list[dict[str, str]]) -> str:
    provider = getenv("DIGEST_PROVIDER", "auto").lower()
    openai_ready = bool(getenv("OPENAI_API_KEY"))
    tencent_ready = has_tencent_credentials()
    print(
        "Digest provider selection: "
        f"requested={provider}, openai_configured={openai_ready}, tencent_configured={tencent_ready}"
    )

    if provider in {"tencent", "tmt", "tencent-tmt"}:
        if not tencent_ready:
            print("DIGEST_PROVIDER=tencent was requested, but Tencent secrets are missing.", file=sys.stderr)
            return fallback_digest(rows)
        return tencent_digest(rows)

    if provider == "openai":
        return ai_digest(rows)

    if provider not in {"auto", ""}:
        print(f"Unknown DIGEST_PROVIDER={provider!r}; using auto.", file=sys.stderr)

    return ai_digest(rows)


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
    today = dt.datetime.now(LOCAL_TZ).date().isoformat()
    items = fetch_items(token)
    rows = normalize_items(items)
    body = make_digest(rows)
    subject = f"The Old Reader Daily Radar - {today} - {len(rows)} latest items"
    send_email(subject, body)
    print(f"Sent digest with {len(rows)} normalized latest items.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(f"HTTP request failed with status {status}.", file=sys.stderr)
        raise
