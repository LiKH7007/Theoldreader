# The Old Reader 每日邮件 Action

这个仓库用于每天自动读取 The Old Reader 未读条目，整理成一封邮件发给你。

核心原理很简单：

1. GitHub Actions 按定时规则启动一台临时 Linux 机器。
2. 这台机器运行 `scripts/daily_theoldreader.py`。
3. 脚本用 `TOR_TOKEN` 访问 The Old Reader API。
4. 如果配置了 `OPENAI_API_KEY`，脚本会生成中文文献雷达摘要。
5. 如果没配置 OpenAI，但配置了腾讯云机器翻译，脚本会把标题和摘要翻译成中文。
6. 如果两者都没配置，脚本会发送基础列表。
7. 脚本用 SMTP 把结果发到你的邮箱。

注意：Codex skill 本身不能直接作为 GitHub Actions 运行。skill 是“给 Codex 看的说明书”，Actions 能运行的是脚本，所以这里已经把流程写成了 Python 脚本。

## 第 0 步：确认仓库文件

仓库里应当有这些文件：

```text
.github/workflows/daily.yml
scripts/daily_theoldreader.py
scripts/get_tor_token.py
requirements.txt
README.md
```

`.github/workflows/daily.yml` 是每天定时运行的入口。

`scripts/daily_theoldreader.py` 是真正抓取、摘要、发邮件的脚本。

`scripts/get_tor_token.py` 是本地获取 The Old Reader token 的小工具，只在你电脑上运行。

## 第 1 步：获取 The Old Reader Token

The Old Reader 官方 API 使用 Google Reader 风格认证。请求时需要把 token 放到请求头里：

```text
Authorization: GoogleLogin auth=TOKEN
```

如果你的 The Old Reader 账号只用 Google 或 Facebook 登录，需要先到 The Old Reader 的设置里设置用户名和密码。官方说明也提示：第三方 App/API 需要用户名和密码。

在本仓库目录打开 PowerShell：

```powershell
cd E:\a_codex\day-by-day\Codex-linux\Theoldreader
python -m pip install -r requirements.txt
python scripts\get_tor_token.py --email "你的 The Old Reader 邮箱"
```

然后它会提示：

```text
The Old Reader password:
```

输入密码后，终端会输出一串 token。这个 token 后面要填到 GitHub Secrets 里的 `TOR_TOKEN`。

不要把 token 写进代码、README、截图或聊天记录。

## 第 2 步：准备发件邮箱 SMTP

你需要一个能通过 SMTP 发邮件的邮箱。

常见配置示例：

```text
QQ 邮箱:
SMTP_HOST = smtp.qq.com
SMTP_PORT = 465
SMTP_SSL  = true
SMTP_USER = 你的 QQ 邮箱
SMTP_PASSWORD = QQ 邮箱的 SMTP 授权码

163 邮箱:
SMTP_HOST = smtp.163.com
SMTP_PORT = 465
SMTP_SSL  = true
SMTP_USER = 你的 163 邮箱
SMTP_PASSWORD = 163 邮箱的 SMTP 授权码

Gmail:
SMTP_HOST = smtp.gmail.com
SMTP_PORT = 465
SMTP_SSL  = true
SMTP_USER = 你的 Gmail
SMTP_PASSWORD = Gmail App Password
```

重要：`SMTP_PASSWORD` 通常不是网页登录密码，而是邮箱后台生成的“授权码”或“应用专用密码”。

## 第 3 步：配置 GitHub Secrets

打开你的 GitHub 仓库：

[LiKH7007/Theoldreader](https://github.com/LiKH7007/Theoldreader)

进入：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

逐个添加这些 Secrets：

| 名称 | 必填 | 填什么 |
| --- | --- | --- |
| `TOR_TOKEN` | 是 | 第 1 步得到的 The Old Reader token |
| `SMTP_HOST` | 是 | SMTP 服务器，例如 `smtp.qq.com` |
| `SMTP_PORT` | 是 | SMTP 端口，通常是 `465` |
| `SMTP_USER` | 是 | 发件邮箱账号 |
| `SMTP_PASSWORD` | 是 | 邮箱 SMTP 授权码 |
| `MAIL_FROM` | 是 | 发件人邮箱，通常和 `SMTP_USER` 一样 |
| `MAIL_TO` | 是 | 收件人邮箱 |
| `OPENAI_API_KEY` | 否 | 配了会生成 AI 中文摘要，不配也能发基础列表 |
| `TENCENT_SECRET_ID` | 否 | 腾讯云 API 密钥 SecretId |
| `TENCENT_SECRET_KEY` | 否 | 腾讯云 API 密钥 SecretKey |

如果你想用腾讯云翻译，至少添加：

```text
TENCENT_SECRET_ID
TENCENT_SECRET_KEY
```

注意：`SecretKey` 只在腾讯云创建密钥时显示一次，后面不能再次查看。不要发到聊天里，也不要写进仓库。

## 第 4 步：配置可选 Variables

进入：

```text
Settings -> Secrets and variables -> Actions -> Variables
```

可以添加这些 Variables：

| 名称 | 默认值 | 说明 |
| --- | --- | --- |
| `OPENAI_MODEL` | `gpt-4.1-mini` | 生成中文摘要用的模型 |
| `SMTP_SSL` | `true` | 是否使用 SMTP SSL |
| `TOR_LIMIT` | `100` | 从 The Old Reader 最多抓多少条 |
| `TOR_MAX_ITEMS` | `30` | 邮件里最多处理多少条 |
| `TENCENT_REGION` | `ap-beijing` | 腾讯云机器翻译地域 |
| `TENCENT_TARGET` | `zh` | 腾讯云目标语言，中文用 `zh` |
| `DIGEST_PROVIDER` | `auto` | 摘要/翻译来源，可填 `auto`、`openai`、`tencent` |

不想折腾的话，这一步可以先跳过。

如果 `OPENAI_API_KEY` 没配、填错或额度不足，脚本会自动尝试腾讯云翻译。腾讯云也没配置时，才退回基础列表邮件。

如果你想强制使用腾讯云翻译，不管是否配置了 OpenAI，请添加 Variable：

```text
DIGEST_PROVIDER = tencent
```

运行日志里会出现类似：

```text
Digest provider selection: requested=tencent, openai_configured=False, tencent_configured=True
```

邮件正文里会出现：

```text
翻译服务：腾讯云机器翻译
```

## 第 4.1 步：开通腾讯云机器翻译

如果你想用腾讯云免费额度做中文翻译，按这个流程：

1. 打开 [腾讯云机器翻译快速入门](https://cloud.tencent.com/document/product/551/104415)。
2. 登录腾讯云账号，并完成实名。
3. 进入机器翻译控制台，勾选服务协议后开通服务。
4. 打开 [API 密钥管理](https://console.cloud.tencent.com/cam/capi)。
5. 点击 `新建密钥`。
6. 保存 `SecretId` 和 `SecretKey`。
7. 回到 GitHub 仓库，添加 Repository secrets：

```text
TENCENT_SECRET_ID = 你的 SecretId
TENCENT_SECRET_KEY = 你的 SecretKey
```

腾讯云官方文档当前说明：文本翻译有免费额度，免费额度用完后，后付费默认关闭；如未开启后付费，一般会停服而不是自动扣费。具体以你的腾讯云控制台为准。

## 第 5 步：手动运行一次测试

第一次建议手动运行，不要等第二天。

操作：

1. 打开 GitHub 仓库页面。
2. 点击 `Actions`。
3. 左侧选择 `Daily The Old Reader Radar`。
4. 点击右侧 `Run workflow`。
5. 等它运行结束。
6. 查看邮箱是否收到邮件。

如果失败，点进失败的运行日志，看最后几行错误。

常见错误：

```text
Missing required environment variable or GitHub Secret: TOR_TOKEN
```

说明 GitHub Secrets 里没有配置 `TOR_TOKEN`，或者名字拼错了。

```text
HTTP request failed with status 403
```

通常是 `TOR_TOKEN` 错了、过期了，或者 The Old Reader 账号/API 认证失败。

```text
SMTPAuthenticationError
```

通常是邮箱账号或 SMTP 授权码错了。

```text
OpenAI summarization failed; sending fallback digest instead
```

说明 AI 摘要失败了。脚本会继续尝试腾讯云翻译；如果腾讯云没配置，则发送基础列表邮件。可以稍后再检查 `OPENAI_API_KEY` 或 `OPENAI_MODEL`。

```text
Tencent translation failed; sending fallback digest instead
```

说明腾讯云翻译失败了，但脚本会继续发送基础列表邮件。常见原因是 `TENCENT_SECRET_ID` / `TENCENT_SECRET_KEY` 填错、机器翻译服务没开通、地域配置不合适，或免费额度用完。

```text
Node.js 20 is deprecated
```

这是 GitHub Actions 官方 action 版本的提示，不是脚本失败原因。当前 workflow 已经使用新版 `actions/checkout` 和 `actions/setup-python`。

## 第 6 步：确认每天定时

当前定时配置在 `.github/workflows/daily.yml`：

```yaml
- cron: "0 23 * * *"
```

GitHub Actions cron 使用 UTC 时间。北京时间 = UTC + 8。

所以 `0 23 * * *` 的意思是：

```text
每天 UTC 23:00
每天北京时间 07:00
```

如果你想改成北京时间 08:30：

```yaml
- cron: "30 0 * * *"
```

如果你想改成北京时间 21:00：

```yaml
- cron: "0 13 * * *"
```

## 第 7 步：以后怎么让 Codex 修改

你可以直接把下面这段话发给 Codex：

```text
请继续维护我的 GitHub 仓库 LiKH7007/Theoldreader。目标是每天通过 GitHub Actions 读取 The Old Reader 未读条目并发送邮件。请先检查 .github/workflows/daily.yml、scripts/daily_theoldreader.py 和 README.md。不要把任何 token、邮箱授权码、OpenAI Key 写进仓库。修改后请运行 python -m py_compile scripts/daily_theoldreader.py，并告诉我需要在 GitHub Secrets 里配置什么。
```

如果你想让 Codex 直接提交：

```text
请把本地修改提交并推送到 GitHub 仓库 LiKH7007/Theoldreader。提交前请先 git status，确认没有密钥或临时文件。
```

## 常见问题：PowerShell 提示找不到 git

如果你在 PowerShell 里运行：

```powershell
git push origin main
```

看到：

```text
无法将“git”项识别为 cmdlet、函数、脚本文件或可运行程序的名称
```

说明你的普通 PowerShell 找不到 Git。解决方法有两个。

方法 A：直接使用 Codex 内置 Git 的完整路径：

```powershell
cd E:\a_codex\day-by-day\Codex-linux\Theoldreader
& "C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe" push origin main
```

如果弹出 GitHub 登录窗口，按提示登录即可。

方法 B：安装 Git for Windows：

1. 打开 [Git for Windows](https://git-scm.com/download/win)。
2. 安装时保持默认选项即可。
3. 重新打开 PowerShell。
4. 运行：

```powershell
git --version
cd E:\a_codex\day-by-day\Codex-linux\Theoldreader
git push origin main
```

## 参考

- [The Old Reader Apps](https://www.theoldreader.com/en/apps/)：说明它提供 Google Reader 风格 API，并提示第三方 App/API 需要用户名密码。
- [The Old Reader API](https://github.com/theoldreader/api)：说明获取 token 使用 `/accounts/ClientLogin`，请求 API 时使用 `Authorization: GoogleLogin auth=TOKEN`。
- [腾讯云机器翻译快速入门](https://cloud.tencent.com/document/product/551/104415)：说明开通服务、查看密钥和调用方式。
- [腾讯云机器翻译计费概述](https://cloud.tencent.com/document/product/551/35017)：说明文本翻译免费额度和计费逻辑。
- [腾讯云机器翻译请求限制](https://cloud.tencent.com/document/product/551/32572)：说明单次请求字符数限制。
