# The Old Reader 每日文献邮件 Action

这个仓库可以每天自动读取你在 The Old Reader 里订阅的 RSS 文献源，并把最新文献整理成一封 HTML 邮件发给你。

默认规则：

1. 每天北京时间 08:00 自动运行。
2. 只读取 The Old Reader 的 `SUBSCRIPTIONS` 文件夹，不读取 The Old Reader Picks、全站推荐或额外公开 RSS。
3. 默认抓取最近 24 小时的新条目。
4. 默认排除生活、财经、购物、娱乐、系统博客等非学术 feed。
5. 配置 OpenAI 或 DeepSeek 后，会生成中文文献雷达。
6. 腾讯云只作为翻译 fallback，不能真正判断论文重要性。
7. 邮件是 HTML 正文，同时保留纯文本备用版本。
8. 所有 token、邮箱授权码和 API key 都只放在 GitHub Secrets，不要写进仓库。

邮件格式大致是：

```text
一、NPJ COMPUTATIONAL MATERIALS

1. [必读][高] 中文题名
英文题名：original English title
作者：一作：First Author；通讯作者：摘要未说明；作者列表：Author A, Author B, Author C 等
来源：npj Computational Materials | 2026-07-29 | DOI: ...

1. 材料/体系：...
2. 新现象/机制：...
3. 为什么重要：...
4. 证据来源：...
5. 建议：下载精读 / 下载复核 / 扫读图文 / 暂跳过
```

## 0. 适合完全新手看的总流程

你需要做三件事：

1. 把这个仓库复制到自己的 GitHub 账号。
2. 在 GitHub 里填入 The Old Reader、邮箱、AI 服务的密钥。
3. 点一次 `Run workflow` 测试，成功后 GitHub 会每天自动发邮件。

注意：这个流程由 GitHub Actions 在云端运行。配置好以后，你自己的电脑不用每天开机。

## 1. Fork 或下载这个仓库

推荐新手使用 Fork。

1. 打开本仓库页面。
2. 点击右上角 `Fork`。
3. 复制一份到你自己的 GitHub 账号下。
4. 后续所有 Secrets、Variables 和 Actions 都在你自己的 fork 仓库里配置。

如果你熟悉 git，也可以克隆到本地：

```powershell
git clone https://github.com/你的用户名/Theoldreader.git
cd Theoldreader
```

## 2. 准备 Python 环境

你的电脑只需要在第一次获取 The Old Reader token 时用到 Python。

推荐 Python 版本：

```text
Python 3.10 或 3.11
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

## 3. 获取 The Old Reader Token

在本地仓库目录运行：

```powershell
python scripts\get_tor_token.py --email "你的 The Old Reader 邮箱"
```

然后按提示输入 The Old Reader 密码。

程序会输出一串 token。这个 token 后面要填入 GitHub Secret：

```text
TOR_TOKEN
```

不要把 token 写进代码、README、issue、commit message、截图或聊天记录。

如果你的 The Old Reader 账号只用 Google/Facebook 登录，需要先到 The Old Reader 设置里配置可用于 API 登录的邮箱和密码。

## 4. 准备发件邮箱 SMTP

你需要一个能通过 SMTP 发邮件的邮箱。常见邮箱如 163、QQ、Gmail 都可以，但通常需要开启 SMTP 并生成“授权码”。

以 163 邮箱为例：

```text
SMTP_HOST = smtp.163.com
SMTP_PORT = 465
SMTP_SSL = true
SMTP_USER = 你的发件邮箱
SMTP_PASSWORD = 邮箱 SMTP 授权码
MAIL_FROM = 你的发件邮箱
MAIL_TO = 收件邮箱
```

注意：

- `SMTP_PASSWORD` 通常不是网页登录密码，而是邮箱设置里生成的 SMTP 授权码。
- 很多邮箱要求 `MAIL_FROM` 和 `SMTP_USER` 完全一致。

## 5. 配置 GitHub Secrets

进入你自己的 GitHub 仓库：

```text
Settings -> Secrets and variables -> Actions -> Secrets
```

点击 `New repository secret`，添加下面这些。

必填：

| 名称 | 含义 |
| --- | --- |
| `TOR_TOKEN` | The Old Reader API token |
| `SMTP_HOST` | SMTP 服务器，例如 `smtp.163.com` |
| `SMTP_PORT` | SMTP 端口，通常是 `465` |
| `SMTP_USER` | 发件邮箱账号 |
| `SMTP_PASSWORD` | 邮箱 SMTP 授权码 |
| `MAIL_FROM` | 发件人邮箱，通常必须和 `SMTP_USER` 一致 |
| `MAIL_TO` | 收件人邮箱 |

用于生成真正文献判断的 AI，二选一或都填：

| 名称 | 含义 |
| --- | --- |
| `OPENAI_API_KEY` | 用 OpenAI 生成中文文献雷达 |
| `DEEPSEEK_KEY` | 用 DeepSeek 生成中文文献雷达 |

可选翻译 fallback：

| 名称 | 含义 |
| --- | --- |
| `TENCENT_SECRET_ID` | 腾讯云 SecretId |
| `TENCENT_SECRET_KEY` | 腾讯云 SecretKey |

再次提醒：Secrets 只在 GitHub 的 Secret 页面填写，不要写进任何文件。

## 6. 配置 GitHub Variables

进入：

```text
Settings -> Secrets and variables -> Actions -> Variables
```

推荐使用 DeepSeek 时：

```text
DIGEST_PROVIDER = deepseek
DEEPSEEK_MODEL = deepseek-v4-flash
DEEPSEEK_BASE_URL = https://api.deepseek.com
DEEPSEEK_THINKING = false
TOR_SOURCE_MODE = subscriptions_latest
TOR_LOOKBACK_HOURS = 24
TOR_ONLY_UNREAD = false
TOR_MAX_ITEMS = 30
TOR_FETCH_ARTICLE_PAGE = true
TOR_INCLUDE_READER_PICKS = false
TOR_INCLUDE_NON_RESEARCH = false
SMTP_SSL = true
```

推荐使用 OpenAI 时：

```text
DIGEST_PROVIDER = openai
OPENAI_MODEL = gpt-4.1-mini
TOR_SOURCE_MODE = subscriptions_latest
TOR_LOOKBACK_HOURS = 24
TOR_ONLY_UNREAD = false
TOR_MAX_ITEMS = 30
TOR_FETCH_ARTICLE_PAGE = true
TOR_INCLUDE_READER_PICKS = false
TOR_INCLUDE_NON_RESEARCH = false
SMTP_SSL = true
```

如果想自动优先 OpenAI，OpenAI 不可用时尝试 DeepSeek，可以设：

```text
DIGEST_PROVIDER = auto
```

不推荐把 `DIGEST_PROVIDER` 设为 `tencent`，因为腾讯云只翻译标题和摘要，不能判断论文重要性。

## 7. 每个变量是什么意思

| 名称 | 默认值 | 含义 |
| --- | --- | --- |
| `DIGEST_PROVIDER` | `auto` | 摘要来源：`auto`、`openai`、`deepseek`、`tencent` |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI 摘要模型 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | DeepSeek 摘要模型；也可设 `deepseek-v4-pro` |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 地址 |
| `DEEPSEEK_THINKING` | `false` | 是否启用 DeepSeek thinking；日报建议先用 `false` |
| `DEEPSEEK_REASONING_EFFORT` | `high` | 启用 thinking 时的推理强度 |
| `SMTP_SSL` | `true` | 是否使用 SMTP SSL；多数邮箱 465 端口用 `true` |
| `TOR_SOURCE_MODE` | `subscriptions_latest` | 默认读取 The Old Reader 的 `SUBSCRIPTIONS` 最新更新 |
| `TOR_LOOKBACK_HOURS` | `24` | 抓最近多少小时内的新条目 |
| `TOR_ONLY_UNREAD` | `false` | 是否只抓未读；默认不限制已读/未读 |
| `TOR_API_PAGE_SIZE` | `100` | 每个订阅源每次 API 请求抓多少条，最大 1000 |
| `TOR_MAX_PAGES_PER_FEED` | `0` | 单个订阅源最多翻多少页；`0` 表示不设页数上限 |
| `TOR_MAX_ITEMS` | `0` | 邮件最多处理多少篇；`0` 表示不限制 |
| `TOR_MIN_SUMMARY_CHARS` | `120` | RSS 摘要少于多少字符时尝试打开网页补摘要 |
| `TOR_FETCH_ARTICLE_PAGE` | `true` | 摘要不足时是否打开原网页补摘要 |
| `TOR_INCLUDE_READER_PICKS` | `false` | 是否包含 The Old Reader Picks；默认不包含 |
| `TOR_INCLUDE_NON_RESEARCH` | `false` | 是否把非学术条目也放入正文；默认过滤 |
| `TENCENT_REGION` | `ap-beijing` | 腾讯云机器翻译地域 |
| `TENCENT_TARGET` | `zh` | 腾讯云目标语言 |

## 8. 发送时间在哪里改

发送时间在这个文件里改：

```text
.github/workflows/daily.yml
```

找到这一段：

```yaml
on:
  schedule:
    # 08:00 Beijing time every day. GitHub Actions cron uses UTC.
    - cron: "0 0 * * *"
```

真正控制时间的是这一行：

```yaml
- cron: "0 0 * * *"
```

GitHub Actions 的 cron 使用 UTC 时间，不是北京时间。

北京时间 = UTC + 8。

所以当前：

```text
UTC 00:00 = 北京时间 08:00
```

常见修改示例：

| 想要的北京时间 | 应该写的 cron |
| --- | --- |
| 每天 07:00 | `0 23 * * *` |
| 每天 08:00 | `0 0 * * *` |
| 每天 12:00 | `0 4 * * *` |
| 每天 21:00 | `0 13 * * *` |
| 每天 23:30 | `30 15 * * *` |

修改步骤：

1. 打开 GitHub 仓库页面。
2. 进入 `.github/workflows/daily.yml`。
3. 点击右上角铅笔图标编辑。
4. 修改 `cron` 那一行。
5. 点击 `Commit changes` 保存。

如果你不会换算，记住：

```text
UTC 小时 = 北京时间小时 - 8
```

如果结果是负数，就加 24。

例如北京时间 07:00：

```text
7 - 8 = -1
-1 + 24 = 23
cron = 0 23 * * *
```

## 9. 手动运行测试

配置完成后，先不要等第二天，手动跑一次。

进入：

```text
Actions -> Daily The Old Reader Radar -> Run workflow
```

然后等待运行结束。

如果成功，你会收到邮件。

如果失败，点击失败的 job，看日志最后几行。日志不会打印 Secrets。

正常日志里你应该看到类似：

```text
Subscription latest mode: subscriptions=...
Digest provider selection: requested=deepseek, ...
Sent digest with ... normalized latest items.
```

如果看到：

```text
DIGEST_PROVIDER: tencent
```

说明你还在用腾讯云翻译，不会得到真正的文献重要性判断。

## 10. 常见错误

### Missing required environment variable or GitHub Secret

说明对应 Secret 没有配置，或者名字拼错。

### Mail from address must be same as authorization user

说明 `MAIL_FROM` 和 `SMTP_USER` 不一致。很多邮箱要求它们完全相同。

### HTTP request failed with status 403

通常是 `TOR_TOKEN` 错误、过期，或者 The Old Reader API 认证失败。

### OpenAI summarization failed

OpenAI 调用失败。常见原因是 API 没余额、429 限流或 key 配错。脚本会优先尝试 DeepSeek fallback。

### DeepSeek summarization failed

DeepSeek 调用失败。检查：

- `DEEPSEEK_KEY` 是否在 Secrets 里；
- `DIGEST_PROVIDER` 是否是 `deepseek` 或 `auto`；
- `DEEPSEEK_BASE_URL` 是否是 `https://api.deepseek.com`；
- DeepSeek 账户是否有余额或额度。

### Tencent translation failed

腾讯云翻译失败。脚本会退回结构化未评分列表。

### FailedOperation.UserNotRegistered

腾讯云机器翻译 TMT 服务还没开通，需要进入腾讯云控制台开通。

## 11. 文件结构

```text
.github/workflows/daily.yml
scripts/daily_theoldreader.py
scripts/get_tor_token.py
requirements.txt
README.md
docs/TheOldReader_Daily_Radar_User_Guide.pdf
```

其中：

- `.github/workflows/daily.yml`：GitHub Actions 定时入口，也是修改发送时间的地方。
- `scripts/daily_theoldreader.py`：真正抓取、总结、发邮件的脚本。
- `scripts/get_tor_token.py`：本地获取 The Old Reader token 的工具。
- `docs/TheOldReader_Daily_Radar_User_Guide.pdf`：PDF 版教程。

## 12. 参考

- [The Old Reader Apps](https://www.theoldreader.com/en/apps/)
- [The Old Reader API](https://github.com/theoldreader/api)
- [DeepSeek API Docs](https://api-docs.deepseek.com/)
- [腾讯云机器翻译快速入门](https://cloud.tencent.com/document/product/551/104415)
