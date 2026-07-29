# The Old Reader 每日文献邮件 Action
-------------------------------------------------------------
1. Fork 或下载你的仓库
让他先打开你的仓库：
LiKH7007/Theoldreader
然后点右上角 Fork，复制一份到自己的 GitHub 账号下。
或者用 git 下载到本地：
git clone https://github.com/他的用户名/Theoldreader.git
cd Theoldreader
2. 准备 Python 环境
电脑上需要有 Python 3.10 或 3.11。
安装依赖：
python -m pip install -r requirements.txt
3. 获取 The Old Reader Token
运行：
python scripts\get_tor_token.py --email "他的 The Old Reader 邮箱"
然后根据提示输入 The Old Reader 密码。
程序会输出一个 token。这个 token 只能放进 GitHub Secrets，不能写进代码、README、截图、聊天记录。
4. 准备发件邮箱 SMTP
他需要一个可以 SMTP 发邮件的邮箱，比如 163、QQ、Gmail 等。
以 163 邮箱为例，通常是：
SMTP_HOST = smtp.163.com
SMTP_PORT = 465
SMTP_SSL = true
SMTP_USER = 他的发件邮箱
SMTP_PASSWORD = 邮箱 SMTP 授权码
MAIL_FROM = 他的发件邮箱
MAIL_TO = 接收文献邮件的邮箱
注意：SMTP_PASSWORD 通常不是网页登录密码，而是邮箱里单独生成的“SMTP 授权码”
----------------------------------------------------------------
这个仓库用于每天自动读取 The Old Reader 的订阅源最新更新，并把摘要整理成邮件发送。

当前默认规则：

1. 每天北京时间 08:00 自动运行。
2. 读取 The Old Reader `SUBSCRIPTIONS` 文件夹中的所有订阅源，不限定具体期刊。
3. “不限定订阅源”指不限定 `SUBSCRIPTIONS` 文件夹里的期刊/出版社 feed，不是抓取 The Old Reader Picks、全站推荐或额外公开 RSS。
4. 默认排除 The Old Reader Picks，例如 Apartment Therapy、Man of Many、The Old Reader blog 等。
5. 默认抓取最近 24 小时内的最新条目。
6. 默认不限制邮件条目数量；当天识别到多少文献就处理多少。
7. 只总结 RSS 摘要或网页摘要，不下载、不读取 PDF。
8. 如果 RSS 摘要太短，脚本会尝试打开原网页补 `meta description`、`citation_abstract` 或 Abstract 段落。
9. 有 `OPENAI_API_KEY` 时优先生成中文文献雷达；没有 OpenAI 时可用腾讯云机器翻译，但腾讯云只做翻译 fallback，不做真正的论文优劣判断；都没有时发送结构化未评分列表。
10. 所有 token、邮箱授权码和 API key 都只放在 GitHub Secrets，不写进仓库。

## 文件结构

```text
.github/workflows/daily.yml
scripts/daily_theoldreader.py
scripts/get_tor_token.py
requirements.txt
README.md
```

`.github/workflows/daily.yml` 是 GitHub Actions 定时入口。

`scripts/daily_theoldreader.py` 是抓取订阅源、补摘要、生成邮件并发送的主脚本。

`scripts/get_tor_token.py` 用于在本地获取 The Old Reader API token，不要在 GitHub Actions 里运行它。

## 默认定时

GitHub Actions cron 使用 UTC 时间。当前配置是：

```yaml
- cron: "0 0 * * *"
```

这表示每天 UTC 00:00，也就是北京时间 08:00。

如果要改成北京时间 07:00：

```yaml
- cron: "0 23 * * *"
```

如果要改成北京时间 21:00：

```yaml
- cron: "0 13 * * *"
```

## GitHub Secrets

进入仓库：

```text
Settings -> Secrets and variables -> Actions -> Secrets
```

添加：

| 名称 | 必填 | 含义 |
| --- | --- | --- |
| `TOR_TOKEN` | 是 | The Old Reader API token |
| `SMTP_HOST` | 是 | SMTP 服务器，例如 `smtp.163.com` |
| `SMTP_PORT` | 是 | SMTP 端口，通常是 `465` |
| `SMTP_USER` | 是 | 发件邮箱账号 |
| `SMTP_PASSWORD` | 是 | 邮箱 SMTP 授权码，不是网页登录密码 |
| `MAIL_FROM` | 是 | 发件人邮箱，通常必须和 `SMTP_USER` 完全一致 |
| `MAIL_TO` | 是 | 收件人邮箱 |
| `OPENAI_API_KEY` | 强烈建议 | 用 OpenAI 生成中文文献雷达；如果要“材料/体系、新现象/机制、为什么重要、证据来源、建议”和重要性判断，就需要它 |
| `TENCENT_SECRET_ID` | 否 | 腾讯云 SecretId |
| `TENCENT_SECRET_KEY` | 否 | 腾讯云 SecretKey |

注意：不要把任何 Secret 写进代码、README、issue、commit message 或截图。

## GitHub Variables

进入：

```text
Settings -> Secrets and variables -> Actions -> Variables
```

可选变量：

| 名称 | 默认值 | 含义 |
| --- | --- | --- |
| `DIGEST_PROVIDER` | `auto` | 摘要来源：`auto`、`openai`、`tencent` |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI 摘要模型 |
| `SMTP_SSL` | `true` | 是否使用 SMTP SSL |
| `TOR_SOURCE_MODE` | `subscriptions_latest` | 抓取模式；默认读取所有订阅源最新更新 |
| `TOR_LOOKBACK_HOURS` | `24` | 抓最近多少小时内的新条目 |
| `TOR_ONLY_UNREAD` | `false` | 是否只抓未读；默认抓最新更新，不限已读/未读 |
| `TOR_API_PAGE_SIZE` | `100` | 每次 API 请求每个订阅源最多取多少条，最大 1000 |
| `TOR_MAX_PAGES_PER_FEED` | `0` | 单个订阅源最多翻多少页；`0` 表示不设页数上限，想加保险丝可设为 `20` |
| `TOR_MAX_ITEMS` | `0` | 邮件最多处理多少条；`0` 表示不限制 |
| `TOR_MIN_SUMMARY_CHARS` | `120` | RSS 摘要少于多少字符时尝试打开网页补摘要 |
| `TOR_FETCH_ARTICLE_PAGE` | `true` | 是否在摘要不足时打开原网页补摘要 |
| `TOR_INCLUDE_READER_PICKS` | `false` | 是否包含 The Old Reader Picks；默认不包含，只看 `SUBSCRIPTIONS` |
| `TOR_INCLUDE_NON_RESEARCH` | `false` | 是否把生活/财经/系统 feed 等非学术条目也放进邮件正文；默认过滤 |
| `TENCENT_REGION` | `ap-beijing` | 腾讯云机器翻译地域 |
| `TENCENT_TARGET` | `zh` | 腾讯云目标语言，中文为 `zh` |

## 推荐配置

如果你有 OpenAI：

```text
DIGEST_PROVIDER = auto
OPENAI_MODEL = gpt-4.1-mini
TOR_SOURCE_MODE = subscriptions_latest
TOR_LOOKBACK_HOURS = 24
TOR_ONLY_UNREAD = false
TOR_MAX_ITEMS = 0
TOR_FETCH_ARTICLE_PAGE = true
TOR_INCLUDE_READER_PICKS = false
TOR_INCLUDE_NON_RESEARCH = false
```

这是推荐模式。只有 OpenAI 模式才会对每篇论文做真正的五项判断和重要性分级。

如果不用 OpenAI，只想翻译摘要：

```text
DIGEST_PROVIDER = tencent
TENCENT_REGION = ap-beijing
TENCENT_TARGET = zh
```

这种模式只翻译标题和摘要，不会真正判断论文优劣。脚本仍会先过滤 The Old Reader Picks 和明显非学术条目，避免把生活资讯翻译成文献简报。

## 阅读准则

OpenAI 模式下，邮件会按文献雷达格式输出：

```text
[必读]
[值得下载]
[扫读即可]
[跳过]
```

推荐条目会尽量说明：

```text
材料/体系
新现象/机制
为什么重要
证据来源
建议动作
```

OpenAI 模式下，每篇进入 `[必读]`、`[值得下载]`、`[扫读即可]` 的研究条目都必须按下面五项输出，并给出 `[高] / [中高] / [中] / [低]` 重要性标签：

```text
### [必读][高] 论文中文题名
**来源：** 订阅源 | reader date | DOI/link

- **材料/体系：** ...
- **新现象/机制：** ...
- **为什么重要：** ...
- **证据来源：** ...
- **建议：** 下载精读 / 下载复核 / 扫读图文 / 暂跳过
```

如果摘要不足，邮件会明确写：

```text
摘要不足，需要打开网页复核
```

脚本不会下载或读取 PDF。

如果订阅源里混有生活、购物、财经、娱乐或 The Old Reader 系统 feed，默认不会进入文献雷达正文，只会在邮件末尾显示“已过滤”数量。如果你确实想审计所有订阅更新，可以把 `TOR_INCLUDE_NON_RESEARCH` 设为 `true`。

## 手动运行测试

1. 打开 GitHub 仓库页面。
2. 点击 `Actions`。
3. 选择 `Daily The Old Reader Radar`。
4. 点击 `Run workflow`。
5. 等待运行结束。
6. 检查邮箱是否收到邮件。

## 常见错误

```text
Missing required environment variable or GitHub Secret: TOR_TOKEN
```

说明 GitHub Secrets 中没有配置 `TOR_TOKEN`，或者名字写错。

```text
Mail from address must be same as authorization user
```

说明 `MAIL_FROM` 和 `SMTP_USER` 不一致。很多邮箱要求二者完全相同。

```text
HTTP request failed with status 403
```

通常是 `TOR_TOKEN` 错误、过期，或者 The Old Reader API 认证失败。

```text
OpenAI summarization failed; trying Tencent translation instead
```

说明 OpenAI 摘要失败，脚本会尝试腾讯云翻译 fallback。

```text
Tencent translation failed; sending fallback digest instead
```

说明腾讯云翻译失败，脚本会退回结构化未评分列表，不做重要性判断。

```text
FailedOperation.UserNotRegistered: Service has not been opened
```

说明腾讯云机器翻译服务还没开通，需要进入控制台开通 TMT。

## 参考

- [The Old Reader Apps](https://www.theoldreader.com/en/apps/)
- [The Old Reader API](https://github.com/theoldreader/api)
- [腾讯云机器翻译快速入门](https://cloud.tencent.com/document/product/551/104415)
- [腾讯云机器翻译计费概述](https://cloud.tencent.com/document/product/551/35017)
