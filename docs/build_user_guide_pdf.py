from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUT = Path(__file__).with_name("TheOldReader_Daily_Radar_User_Guide.pdf")


def register_font() -> str:
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    ]
    for font in candidates:
        if font.exists():
            pdfmetrics.registerFont(TTFont("CN", str(font)))
            return "CN"
    return "Helvetica"


FONT = register_font()


def p(text: str, style: ParagraphStyle):
    return Paragraph(text.replace("\n", "<br/>"), style)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
    )
    base = getSampleStyleSheet()
    title = ParagraphStyle("TitleCN", parent=base["Title"], fontName=FONT, fontSize=20, leading=28, alignment=TA_LEFT)
    h1 = ParagraphStyle("H1CN", parent=base["Heading1"], fontName=FONT, fontSize=15, leading=22, spaceBefore=12)
    h2 = ParagraphStyle("H2CN", parent=base["Heading2"], fontName=FONT, fontSize=12.5, leading=18, spaceBefore=8)
    body = ParagraphStyle("BodyCN", parent=base["BodyText"], fontName=FONT, fontSize=9.5, leading=15)
    small = ParagraphStyle("SmallCN", parent=body, fontSize=8.5, leading=13)
    code = ParagraphStyle("CodeCN", parent=body, fontName=FONT, fontSize=8.5, leading=13, backColor=colors.whitesmoke)

    story = []
    story.append(p("The Old Reader 每日文献雷达使用教程", title))
    story.append(p("适用于 GitHub 仓库 LiKH7007/Theoldreader。本文不包含任何 token、邮箱授权码、SecretId、SecretKey 或 OpenAI Key。", body))
    story.append(Spacer(1, 8))

    story.append(p("1. 这个 Action 做什么", h1))
    story.append(p(
        "GitHub Actions 每天北京时间 08:00 启动，读取 The Old Reader 的 SUBSCRIPTIONS 文件夹中的所有订阅源，抓取最近 24 小时内的最新条目。"
        "不限定订阅源指不限定 SUBSCRIPTIONS 里的期刊/出版社 feed，不是抓取 The Old Reader Picks、全站推荐或额外公开 RSS。"
        "若配置 OpenAI，则每篇文献按材料/体系、新现象/机制、为什么重要、证据来源、建议五项输出，并给出重要性标签。"
        "若只配置腾讯云机器翻译，则只是翻译 fallback，不能可靠判断论文重要性；都没有时发送结构化未评分列表。",
        body,
    ))

    story.append(p("2. 必须配置的 GitHub Secrets", h1))
    secrets = [
        ["名称", "含义", "注意事项"],
        ["TOR_TOKEN", "The Old Reader API token", "通过本地 get_tor_token.py 获取；不要写进仓库"],
        ["SMTP_HOST", "SMTP 服务器", "如 smtp.163.com、smtp.qq.com、smtp.gmail.com"],
        ["SMTP_PORT", "SMTP 端口", "SSL 通常 465"],
        ["SMTP_USER", "发件邮箱账号", "通常必须与 MAIL_FROM 相同"],
        ["SMTP_PASSWORD", "SMTP 授权码", "不是网页登录密码"],
        ["MAIL_FROM", "发件人邮箱", "若报 Mail from address must be same as authorization user，就改成和 SMTP_USER 一致"],
        ["MAIL_TO", "收件人邮箱", "可填一个或多个收件人"],
    ]
    story.append(Table([[p(c, small) for c in row] for row in secrets], colWidths=[4 * cm, 5 * cm, 7.5 * cm], style=[
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))

    story.append(p("3. 可选的 AI / 翻译 Secrets", h1))
    story.append(p("OPENAI_API_KEY：配置后可生成真正的中文文献雷达，包括材料/体系、新现象/机制、重要性、证据与建议。", body))
    story.append(p("TENCENT_SECRET_ID 与 TENCENT_SECRET_KEY：配置后可用腾讯云机器翻译作为 fallback。腾讯云只能翻译标题和摘要，不能替代科学判断。", body))

    story.append(PageBreak())
    story.append(p("4. GitHub Variables 参数说明", h1))
    vars_table = [
        ["变量", "默认值", "作用"],
        ["DIGEST_PROVIDER", "auto", "摘要来源：auto、openai、tencent。auto 会优先 OpenAI，再腾讯云，再结构化未评分列表。"],
        ["OPENAI_MODEL", "gpt-4.1-mini", "OpenAI 摘要模型。"],
        ["SMTP_SSL", "true", "是否使用 SMTP SSL。大多数邮箱 465 端口用 true。"],
        ["TOR_SOURCE_MODE", "subscriptions_latest", "默认读取 SUBSCRIPTIONS 文件夹的最新更新，不扩展公开 RSS。"],
        ["TOR_LOOKBACK_HOURS", "24", "抓最近多少小时内的新条目。每天运行一次时建议 24。"],
        ["TOR_ONLY_UNREAD", "false", "是否只抓未读。默认 false，表示按最新更新抓，不看已读/未读。"],
        ["TOR_API_PAGE_SIZE", "100", "每个订阅源每次 API 请求抓多少条，最大 1000。"],
        ["TOR_MAX_PAGES_PER_FEED", "0", "单个订阅源最多翻多少页；0 表示不设页数上限，想加保险丝可设为 20。"],
        ["TOR_MAX_ITEMS", "0", "邮件最多处理多少条。0 表示不人为限制数量。"],
        ["TOR_MIN_SUMMARY_CHARS", "120", "RSS 摘要低于该长度时，尝试打开原网页补摘要。"],
        ["TOR_FETCH_ARTICLE_PAGE", "true", "是否在摘要不足时请求文章网页。"],
        ["TOR_INCLUDE_READER_PICKS", "false", "是否包含 The Old Reader Picks；默认 false，只看 SUBSCRIPTIONS。"],
        ["TOR_INCLUDE_NON_RESEARCH", "false", "是否把非学术 feed 也放进正文；默认 false，只在末尾报告过滤数量。"],
        ["TENCENT_REGION", "ap-beijing", "腾讯云机器翻译地域。"],
        ["TENCENT_TARGET", "zh", "腾讯云目标语言，中文为 zh。"],
    ]
    story.append(Table([[p(c, small) for c in row] for row in vars_table], colWidths=[4.3 * cm, 3.1 * cm, 9.1 * cm], repeatRows=1, style=[
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(p("5. 如何修改发送时间", h1))
    story.append(p("GitHub Actions cron 使用 UTC。北京时间 = UTC + 8。当前默认每天北京时间 08:00：", body))
    story.append(p('- cron: "0 0 * * *"', code))
    story.append(p("改成北京时间 07:00：", body))
    story.append(p('- cron: "0 23 * * *"', code))
    story.append(p("改成北京时间 21:00：", body))
    story.append(p('- cron: "0 13 * * *"', code))

    story.append(p("6. 推荐配置", h1))
    story.append(p("有 OpenAI 时：", h2))
    story.append(p(
        "DIGEST_PROVIDER = auto\nOPENAI_MODEL = gpt-4.1-mini\nTOR_SOURCE_MODE = subscriptions_latest\nTOR_LOOKBACK_HOURS = 24\nTOR_ONLY_UNREAD = false\nTOR_MAX_ITEMS = 0\nTOR_FETCH_ARTICLE_PAGE = true\nTOR_INCLUDE_READER_PICKS = false\nTOR_INCLUDE_NON_RESEARCH = false",
        code,
    ))
    story.append(p("只用腾讯云翻译时（只能翻译，不能做重要性判断）：", h2))
    story.append(p("DIGEST_PROVIDER = tencent\nTENCENT_REGION = ap-beijing\nTENCENT_TARGET = zh\nTOR_INCLUDE_NON_RESEARCH = false", code))

    story.append(PageBreak())
    story.append(p("7. 运行测试", h1))
    story.append(p(
        "打开 GitHub 仓库 -> Actions -> Daily The Old Reader Radar -> Run workflow。运行结束后检查邮箱。"
        "如果失败，点进失败的 job，看日志最后几行。日志不会打印 secrets。",
        body,
    ))

    story.append(p("8. 常见错误", h1))
    errors = [
        ["错误", "解释与处理"],
        ["Missing required environment variable or GitHub Secret", "对应 Secret 没有配置，或名字拼错。"],
        ["Mail from address must be same as authorization user", "MAIL_FROM 必须和 SMTP_USER 完全一致。"],
        ["HTTP request failed with status 403", "TOR_TOKEN 错误、过期，或 The Old Reader API 认证失败。"],
        ["OpenAI summarization failed", "OpenAI 调用失败；脚本会尝试腾讯云 fallback。"],
        ["FailedOperation.UserNotRegistered", "腾讯云机器翻译 TMT 服务未开通。"],
    ]
    story.append(Table([[p(c, small) for c in row] for row in errors], colWidths=[6.2 * cm, 10.3 * cm], style=[
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    story.append(p("9. 安全提醒", h1))
    story.append(p(
        "不要把 TOR_TOKEN、SMTP_PASSWORD、TENCENT_SECRET_KEY、OPENAI_API_KEY 发到聊天、写进 README、提交到 git 或放进截图。"
        "如果泄露，应立即在对应服务中重置。",
        body,
    ))

    doc.build(story)
    print(OUT)


if __name__ == "__main__":
    main()
