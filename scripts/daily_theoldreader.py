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
ACADEMIC_FEED_RE = re.compile(
    r"journal|materials?|materialia|nature|npj|wiley|sciencedirect|elsevier|springer|"
    r"acs|rsc|aip|aps|iop|arxiv|pubmed|science|cell|advanced|nano|energy|chem|"
    r"physics|physical review|acta|scripta|ceramics|metallurgy|biomaterials",
    re.I,
)
ACADEMIC_URL_RE = re.compile(
    r"doi\.org|nature\.com|sciencedirect\.com|onlinelibrary\.wiley\.com|"
    r"springer\.com|acs\.org|rsc\.org|aip\.org|aps\.org|iopscience|arxiv\.org|"
    r"pubs\.acs|tandfonline|mdpi\.com|frontiersin|science\.org|cell\.com",
    re.I,
)
RESEARCH_TEXT_RE = re.compile(
    r"\b(abstract|we report|we demonstrate|we show|we find|this study|in this work|"
    r"synthesis|characterization|density functional|DFT|molecular dynamics|"
    r"microscopy|spectroscopy|electrochemical|photocatal|perovskite|alloy|oxide|"
    r"nanoparticle|heterostructure|phase transition|microstructure|phonon|thermal)\b",
    re.I,
)
NON_ACADEMIC_FEED_RE = re.compile(
    r"apartment therapy|get rich slowly|what if\?|the old reader|daily what|"
    r"man of many|cheezburger|shopping|decor|home|lifestyle|personal finance|"
    r"sneakers|food|travel|entertainment",
    re.I,
)
READER_PICKS_RE = re.compile(
    r"the old reader picks|apartment therapy|get rich slowly|what if\?|the old reader:|"
    r"the daily what|man of many|cheezburger",
    re.I,
)
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


def subscription_scope_text(sub: dict[str, Any]) -> str:
    parts = [str(sub.get("title", "")), str(sub.get("id", "")), str(sub.get("htmlUrl", ""))]
    for category in sub.get("categories", []) or []:
        if isinstance(category, dict):
            parts.append(str(category.get("label", "")))
            parts.append(str(category.get("id", "")))
        else:
            parts.append(str(category))
    return " ".join(parts)


def is_user_subscription(sub: dict[str, Any]) -> bool:
    """Keep the user's SUBSCRIPTIONS by default; exclude The Old Reader Picks."""

    if as_bool("TOR_INCLUDE_READER_PICKS", False):
        return True
    return not READER_PICKS_RE.search(subscription_scope_text(sub))


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
    raw_subscriptions = fetch_subscriptions(token)
    subscriptions = [sub for sub in raw_subscriptions if is_user_subscription(sub)]
    print(
        f"Subscription latest mode: subscriptions={len(subscriptions)}/{len(raw_subscriptions)}, "
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


def classify_row(row: dict[str, str]) -> str:
    """Classify an entry before digesting so broad subscriptions stay literature-only."""

    feed = row.get("feed", "")
    title = row.get("title", "")
    url = row.get("url", "")
    summary = row.get("summary", "")

    if ISSUE_RE.search(title):
        return "issue/metadata"
    if NON_ACADEMIC_FEED_RE.search(feed):
        return "non-academic"
    if row.get("doi") or ACADEMIC_FEED_RE.search(feed) or ACADEMIC_URL_RE.search(url):
        return "research-paper"
    if RESEARCH_TEXT_RE.search(f"{title} {summary}"):
        return "academic-adjacent"
    return "non-academic"


def split_literature_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, int]]:
    include_non_research = as_bool("TOR_INCLUDE_NON_RESEARCH", False)
    kept: list[dict[str, str]] = []
    skipped = {"non-academic": 0, "issue/metadata": 0}

    for row in rows:
        item_class = classify_row(row)
        row["item_class"] = item_class
        if include_non_research or item_class in {"research-paper", "academic-adjacent"}:
            kept.append(row)
        else:
            skipped[item_class] = skipped.get(item_class, 0) + 1

    return kept, skipped


def skipped_note(skipped: dict[str, int]) -> str:
    total = sum(skipped.values())
    if total <= 0:
        return ""
    lines = ["", "## 已过滤", ""]
    if skipped.get("non-academic", 0):
        lines.append(f"- 非学术/生活/系统订阅源：{skipped['non-academic']} 条，未进入文献雷达正文。")
    if skipped.get("issue/metadata", 0):
        lines.append(f"- 期刊目录、封面、勘误或 issue metadata：{skipped['issue/metadata']} 条，已跳过。")
    return "\n".join(lines)


def no_literature_digest(original_count: int, skipped: dict[str, int]) -> str:
    return (
        "# The Old Reader Daily Radar\n\n"
        f"今天抓到 {original_count} 条订阅源更新，但没有识别到适合进入文献雷达的学术论文条目。"
        f"{skipped_note(skipped)}"
    ).strip()


def fallback_digest(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "今天 The Old Reader 的订阅源在设定时间窗口内没有抓到新条目。"

    lines = [
        "# The Old Reader Daily Radar",
        "",
        "模式：The Old Reader SUBSCRIPTIONS 最新更新",
        "注意：当前未使用 OpenAI，也未使用腾讯云翻译；以下是结构化基础列表，不能可靠判断论文重要性。",
        "",
    ]
    for row in rows:
        lines.append(f"### [未评分] {row.get('title', '')}")
        source_parts = [part for part in [row.get("feed", ""), row.get("date", ""), row.get("doi") or row.get("url", "")] if part]
        if source_parts:
            lines.append(f"**来源：** {' | '.join(source_parts)}")
        lines.append("")
        lines.append("- **材料/体系：** 未使用 OpenAI，无法可靠抽取。")
        lines.append("- **新现象/机制：** 未使用 OpenAI，无法可靠判断。")
        lines.append("- **为什么重要：** 未评分；需要 OpenAI 或人工阅读摘要后判断。")
        lines.append("- **证据来源：** The Old Reader RSS/网页摘要；未做科学推理。")
        if row.get("summary"):
            lines.append(f"- **建议：** 先按题名相关性决定是否打开链接；摘要片段：{row['summary'][:500]}")
        else:
            lines.append("- **建议：** 摘要不足，需要打开网页复核。")
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
        lines = [
            "# The Old Reader Daily Radar",
            "",
            "模式：The Old Reader SUBSCRIPTIONS 最新更新",
            "翻译服务：腾讯云机器翻译 fallback",
            "注意：当前未使用 OpenAI，以下内容只翻译标题和摘要，不能可靠判断论文重要性。若要材料/体系、新现象/机制和重要性判断，请配置 OPENAI_API_KEY，并设置 DIGEST_PROVIDER=auto 或 openai。",
            "",
        ]
        for index, row in enumerate(rows, 1):
            title_zh = translate_with_tencent(row["title"], target=target)
            time.sleep(0.25)
            summary_zh = ""
            if row["summary"]:
                summary_zh = translate_with_tencent(row["summary"][:1000], target=target)
                time.sleep(0.25)

            lines.append(f"### [未评分] {title_zh or row['title']}")
            lines.append(f"**原题：** {row['title']}")
            if row.get("feed"):
                lines.append(f"**订阅源：** {row['feed']}")
            if row.get("date"):
                lines.append(f"**日期：** {row['date']}")
            if row.get("doi"):
                lines.append(f"**DOI：** {row['doi']}")
            if row.get("url"):
                lines.append(f"**链接：** {row['url']}")
            lines.append("")
            lines.append("- **材料/体系：** 未使用 OpenAI，无法从翻译 fallback 中可靠抽取。")
            lines.append("- **新现象/机制：** 未使用 OpenAI，无法可靠判断；请看下方摘要译文或配置 OpenAI。")
            lines.append("- **为什么重要：** 未评分。腾讯云只做机器翻译，不做科研重要性判断。")
            lines.append("- **证据来源：** The Old Reader RSS/网页摘要的机器翻译。")
            if summary_zh:
                lines.append(f"- **建议：** 暂不据此判断是否下载；若题名与你课题相关，先打开链接看摘要。摘要译文：{summary_zh}")
            else:
                lines.append("- **建议：** 摘要不足，需要打开网页复核。")
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
        2. 来源范围是 The Old Reader 的 SUBSCRIPTIONS 最新更新，不是 The Old Reader Picks，也不是额外扩展的公开 RSS。
        3. 按 [必读]、[值得下载]、[扫读即可]、[跳过] 分组。
        4. 对每篇进入 [必读]、[值得下载]、[扫读即可] 的研究条目，标题行必须带重要性标签：
           ### [必读][高] 中文题名
           ### [值得下载][中高] 中文题名
           ### [扫读即可][中] 中文题名
           重要性标签只能用 [高]、[中高]、[中]、[低]。
        5. 每篇进入 [必读]、[值得下载]、[扫读即可] 的研究条目必须使用完全相同的五项结构，不允许只写摘要：
           - **材料/体系：** 写清具体材料、体系、对象或数据集；未知则写“摘要未说明”。
           - **新现象/机制：** 写清新现象、新机制、新方法或新设计；未知则写“摘要未说明”。
           - **为什么重要：** 给出你对论文重要性的判断，连接到材料科学问题、瓶颈或潜在应用；不要空泛说“很重要”。
           - **证据来源：** 说明依据来自 RSS 摘要、网页摘要、题名推断或摘要不足，并点明实验/计算/表征/模拟/数据集等证据类型。
           - **建议：** 明确写“下载精读 / 下载复核 / 扫读图文 / 暂跳过”，并说明理由。
        6. 每篇研究条目还要保留 DOI 或链接，格式为：
           **来源：** feed | reader date | DOI/link
        7. 如果 summary_source 是 rss_insufficient，必须写“摘要不足，需要打开网页复核”，并且不要列为 [必读]。
        8. 如果是生活、新闻、非学术、纯广告或无法判断的条目，放入 [跳过] 或忽略，并说明已过滤数量。
        9. 输出适合直接作为邮件正文的 Markdown；不要输出“摘要：……”式流水账。

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
    literature_rows, skipped = split_literature_rows(rows)
    if not literature_rows:
        return no_literature_digest(len(rows), skipped)

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
            body = fallback_digest(literature_rows)
        else:
            body = tencent_digest(literature_rows)
        return f"{body}{skipped_note(skipped)}"

    if provider == "openai":
        return f"{ai_digest(literature_rows)}{skipped_note(skipped)}"

    if provider not in {"auto", ""}:
        print(f"Unknown DIGEST_PROVIDER={provider!r}; using auto.", file=sys.stderr)

    return f"{ai_digest(literature_rows)}{skipped_note(skipped)}"


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
