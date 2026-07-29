# The Old Reader 每日文献邮件 Action

这个仓库用于每天自动读取 The Old Reader 的订阅源最新更新，并把摘要整理成邮件发送。

当前默认规则：

1. 每天北京时间 08:00 自动运行。
2. 读取 The Old Reader `SUBSCRIPTIONS` 中所有订阅源，不限定期刊。
3. 默认抓取最近 24 小时内的最新条目。
4. 默认不限制邮件条目数量；当天抓到多少就处理多少。
5. 只总结 RSS 摘要或网页摘要，不下载、不读取 PDF。
6. 如果 RSS 摘要太短，脚本会尝试打开原网页补 `meta description`、`citation_abstract` 或 Abstract 段落。
7. 有 `OPENAI_API_KEY` 时优先生成中文文献雷达；没有 OpenAI 时可用腾讯云机器翻译；都不可用时发送基础列表。
8. 所有 token、邮箱授权码和 API key 都只放在 GitHub Secrets，不写进仓库。

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
| `OPENAI_API_KEY` | 否 | 用 OpenAI 生成中文文献雷达 |
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
```

如果不用 OpenAI，只想翻译摘要：

```text
DIGEST_PROVIDER = tencent
TENCENT_REGION = ap-beijing
TENCENT_TARGET = zh
```

这种模式只翻译标题和摘要，不会真正判断论文优劣。

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
新现象/机制/方法
为什么重要
证据来源
建议动作
```

如果摘要不足，邮件会明确写：

```text
摘要不足，需要打开网页复核
```

脚本不会下载或读取 PDF。

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

说明腾讯云翻译失败，脚本会退回基础英文/原文列表。

```text
FailedOperation.UserNotRegistered: Service has not been opened
```

说明腾讯云机器翻译服务还没开通，需要进入控制台开通 TMT。

## 参考

- [The Old Reader Apps](https://www.theoldreader.com/en/apps/)
- [The Old Reader API](https://github.com/theoldreader/api)
- [腾讯云机器翻译快速入门](https://cloud.tencent.com/document/product/551/104415)
- [腾讯云机器翻译计费概述](https://cloud.tencent.com/document/product/551/35017)
