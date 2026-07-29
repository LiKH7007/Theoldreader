# The Old Reader 每日邮件 Action

这个仓库用于每天自动读取 The Old Reader 未读条目，整理成一封邮件发给你。

核心原理很简单：

1. GitHub Actions 按定时规则启动一台临时 Linux 机器。
2. 这台机器运行 `scripts/daily_theoldreader.py`。
3. 脚本用 `TOR_TOKEN` 访问 The Old Reader API。
4. 如果配置了 `OPENAI_API_KEY`，脚本会生成中文文献雷达摘要；没配置也会发送基础列表。
5. 脚本用 SMTP 把结果发到你的邮箱。

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

不想折腾的话，这一步可以先跳过。

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
