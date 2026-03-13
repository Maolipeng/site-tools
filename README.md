# sitectl

`sitectl` 是一个轻量级 Linux 服务器站点管理 CLI，用于管理 Nginx 站点、Let's Encrypt 证书、手动证书、Node/PM2 应用，以及已有的本地反向代理或 systemd 服务。

它适合这些场景：

- 为域名生成 Nginx 配置
- 自动申请和续期 Let's Encrypt 证书
- 使用 PM2 启动 Node / Next.js / Express / NestJS / Koa 项目
- 托管静态站点
- 代理已有本地服务
- 管理手动证书，例如 Cloudflare Origin CA
- 查看站点状态、日志、健康检查、环境自检
- 导出、导入、回滚站点配置

## 功能概览

- 支持 `node`、`proxy`、`static`、`systemd` 四类站点
- 支持 `letsencrypt` 和 `manual` 两种证书模式
- 支持多域名 `alias`
- 支持显式 IPv6 监听和 IPv6 upstream 回源
- `doctor` 支持探测公网 IPv6，并提示 AAAA 记录、IPv6 监听和 HTTPS 配置建议
- 支持 `create`、`update`、`remove`、`list`、`status`
- 支持 `reload`、`renew`
- 支持 `history`、`rollback`
- 支持 `export`、`import`
- 支持 `logs`、`healthcheck`、`doctor`
- 支持 `cert-info`、`cert-expiring`、`cert-warn`、`cert-verify`、`cert-replace`
- 通过 `/etc/sitectl/sites.json` 持久化本地状态

## 要求

- Python 3.11+
- Linux 服务器
- 已安装并可用的系统命令：
  - `nginx`
  - `certbot`
  - `openssl`
  - `pm2`、`npm`、`node`，仅 `node` 类型需要
  - `systemctl`、`journalctl`，仅 `systemd` 类型和部分运维命令需要

通常需要使用 `root` 或具备相应权限的用户执行，以便写入 `/etc/nginx`、`/etc/sitectl` 并重载 Nginx。

## 安装

### 本地一键安装

```bash
cd /Users/maolipeng/Documents/selfProject/site-tools
./install.sh
```

默认行为：

- 创建本地虚拟环境 `.venv`
- 生成可直接运行的 `sitectl` 启动器
- 自动执行一次 `sitectl --help` smoke test

默认命令路径：

```bash
/Users/maolipeng/Documents/selfProject/site-tools/.venv/bin/sitectl
```

常见变体：

```bash
./install.sh --user
./install.sh --system
./install.sh --venv /opt/sitectl-venv
./install.sh --no-editable
```

说明：

- `--user` 和 `--system` 使用 `pip install`
- 默认 `venv` 模式更适合离线服务器

### `curl | bash` 安装

仓库内置了 bootstrap 脚本 [install.remote.sh](/Users/maolipeng/Documents/selfProject/site-tools/install.remote.sh)。

通过仓库地址安装：

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.remote.sh | \
  SITECTL_REPO_URL=https://github.com/<owner>/<repo> bash
```

直接指定源码压缩包：

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.remote.sh | \
  SITECTL_ARCHIVE_URL=https://github.com/<owner>/<repo>/archive/refs/heads/main.tar.gz bash
```

向内部安装脚本传参：

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.remote.sh | \
  SITECTL_REPO_URL=https://github.com/<owner>/<repo> bash -s -- --user
```

### 传统安装

```bash
git clone <your-repo-url> sitectl
cd sitectl
python3.11 -m venv .venv
source .venv/bin/activate
pip install .
```

开发环境也可以直接运行：

```bash
python -m sitectl --help
```

## Agent Skill

仓库里已经附带了一个 skill，在 [skills/sitectl-ops/SKILL.md](/Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/SKILL.md)。

用途：

- 让大模型在触发 `sitectl` 运维场景时，优先按统一流程调用已有 CLI
- 自动把“先检查、再 dry-run、再执行、再验证”的流程固化下来
- 把 `create` / `update` / `status` / `logs` / `healthcheck` / `cert-*` / `rollback` 这些操作统一成一个 skill 能力

本地安装到 Codex skills 目录：

```bash
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh
```

默认会链接到：

```bash
$CODEX_HOME/skills/sitectl-ops
```

如果没有设置 `CODEX_HOME`，则默认链接到：

```bash
~/.codex/skills/sitectl-ops
```

也支持安装到其他兼容 skill 目录：

```bash
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target claude
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target opencode
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target openclaw
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target agents
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target codex --target claude --target opencode --target openclaw
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target all
```

默认全局安装目录：

- Codex: `~/.codex/skills` 或 `$CODEX_HOME/skills`
- Claude Code 兼容目录: `~/.claude/skills`
- OpenCode 全局目录: `${XDG_CONFIG_HOME:-~/.config}/opencode/skills`
- OpenClaw 全局目录: `~/.openclaw/skills`
- `.agents` 兼容目录: `~/.agents/skills`

也支持项目级安装：

```bash
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target claude --scope project
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target opencode --scope project
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target openclaw --scope project
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target agents --scope project
```

项目级目录分别是：

- Claude Code 兼容目录: `<project>/.claude/skills`
- OpenCode 项目目录: `<project>/.opencode/skills`
- OpenClaw 工作区目录: `<project>/skills`
- `.agents` 项目目录: `<project>/.agents/skills`

安装器还支持：

```bash
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --target opencode --mode copy
bash /Users/maolipeng/Documents/selfProject/site-tools/install-skill.sh --path /custom/skills
```

卸载：

```bash
bash /Users/maolipeng/Documents/selfProject/site-tools/uninstall-skill.sh
```

也支持按 target 卸载：

```bash
bash /Users/maolipeng/Documents/selfProject/site-tools/uninstall-skill.sh --target claude
bash /Users/maolipeng/Documents/selfProject/site-tools/uninstall-skill.sh --target opencode
bash /Users/maolipeng/Documents/selfProject/site-tools/uninstall-skill.sh --target openclaw
bash /Users/maolipeng/Documents/selfProject/site-tools/uninstall-skill.sh --target all
```

skill 内还附带了一组稳定脚本，适合被模型直接调用：

```bash
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py list
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py status app.example.com
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py export --output /tmp/sitectl-bundle.json
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py logs app.example.com --kind error --lines 200
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py cert-warn --days 14
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py preview-update app.example.com --port 9090
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py apply-reload
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py preview-import --input /tmp/sitectl-bundle.json --force
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py apply-rollback app.example.com --backup 20260313153000123456
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_json.py apply-history app.example.com
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_audit.py app.example.com --include-runtime-log
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_cert_report.py --days 14
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_fleet_audit.py --include-runtime-log --only-problems
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_fleet_autofix.py --only-problems --max-priority medium --dry-run-before-apply
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_automation_templates.py --format json
python3 /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_automation_templates.py --format directives --template daily-fleet-audit
bash /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_status.sh app.example.com
bash /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_healthcheck.sh app.example.com --path /healthz
bash /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_cert_verify.sh secure.example.com
bash /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_safe_create.sh --domain api.example.com --type proxy --port 8080 --email ops@example.com --apply
bash /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_safe_update.sh api.example.com --port 9090 --apply
bash /Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/scripts/site_safe_remove.sh api.example.com --apply
```

这些脚本会自动尝试：

- 直接调用 `sitectl`
- 调用仓库 `.venv/bin/sitectl`
- 回退到 `PYTHONPATH=<repo> python3 -m sitectl`

其中：

- `site_json.py` 适合让模型读取结构化结果
- `site_json.py` 现在也支持 `preview-*` 和 `apply-*`，适合结构化计划和执行
- `site_json.py` 的响应现在统一带 `meta.command`、`meta.mode`、`meta.generated_at`、`meta.exit_code`、`meta.trace_id`、`meta.request_id`
- `site_audit.py` 适合一次性拿到站点巡检报告
- `site_audit.py` 现在会返回 `severity`、`next_step_priority`、`recommended_actions` 和 `autofix_candidates`
- `site_cert_report.py` 适合批量证书巡检
- `site_fleet_audit.py` 适合批量站点巡检，并支持 `--domain`、`--match`、`--only-problems`
- `site_fleet_audit.py` 会输出 `global_recommendations` 和 `global_autofix_candidates`
- `site_fleet_autofix.py` 适合批量预览或执行有限的 autofix 候选，支持 `--dry-run-before-apply`
- `site_fleet_autofix.py` 会读取 [autofix-policy.json](/Users/maolipeng/Documents/selfProject/site-tools/skills/sitectl-ops/assets/autofix-policy.json) 策略文件，支持命令白名单、黑名单、域名限制和按命令规则覆盖
- `site_automation_templates.py` 会输出可复用的巡检和证书自动化模板，也支持直接生成 Codex automation 指令
- `site_safe_create.sh` / `site_safe_update.sh` / `site_safe_remove.sh` 适合先 dry-run 再执行

## 命令总览

```bash
sitectl create --domain DOMAIN --type TYPE [options]
sitectl update DOMAIN [options]
sitectl remove DOMAIN [--dry-run]
sitectl list
sitectl status DOMAIN
sitectl reload [--dry-run]
sitectl renew [DOMAIN] [--dry-run]
sitectl history DOMAIN
sitectl rollback DOMAIN --backup BACKUP [--dry-run]
sitectl export [--output FILE]
sitectl import --input FILE [--force] [--dry-run]
sitectl logs DOMAIN [--access|--error|--pm2|--systemd] [--lines N]
sitectl healthcheck DOMAIN [--path PATH] [--timeout N] [--skip-local] [--skip-remote]
sitectl doctor
sitectl cert-info DOMAIN
sitectl cert-expiring [--days N]
sitectl cert-warn [--days N]
sitectl cert-verify DOMAIN
sitectl cert-replace DOMAIN --ssl-cert PATH --ssl-key PATH [--dry-run]
```

IPv6 相关常用参数：

- `--listen-ipv6`
  - 为 Nginx 显式生成 `listen [::]:80;` 和 `listen [::]:443 ssl;`
- `--upstream-host HOST`
  - 为 `node`、`proxy`、`systemd` 指定本地回源地址，例如 `127.0.0.1`、`::1`、`localhost`
- `update` 额外支持 `--no-listen-ipv6`

## 快速开始

### 创建一个 Node 站点

```bash
sitectl create \
  --domain app.example.com \
  --type node \
  --root /srv/app \
  --port 3000 \
  --pm2-name app-example \
  --email ops@example.com
```

### 创建一个已有服务的反向代理站点

```bash
sitectl create \
  --domain api.example.com \
  --type proxy \
  --port 8080 \
  --email ops@example.com
```

### 创建一个启用 IPv6 监听并回源到 `::1` 的代理站点

```bash
sitectl create \
  --domain ipv6.example.com \
  --type proxy \
  --port 8080 \
  --upstream-host ::1 \
  --listen-ipv6 \
  --email ops@example.com
```

### 创建一个静态站点

```bash
sitectl create \
  --domain www.example.com \
  --type static \
  --root /srv/www/example \
  --email ops@example.com
```

### 创建一个手动证书站点

```bash
sitectl create \
  --domain secure.example.com \
  --type proxy \
  --port 8443 \
  --ssl-mode manual \
  --ssl-cert /etc/ssl/certs/cloudflare-origin.pem \
  --ssl-key /etc/ssl/private/cloudflare-origin.key
```

## 站点类型

### `node`

适用于 Next.js / Express / NestJS / Koa 等 Node 项目。

必需参数：

- `--root`
- `--port`
- `--pm2-name`
- `--email`，仅 `letsencrypt` 模式需要

行为：

- 校验 `package.json` 是否存在
- 执行 `npm install`
- 如果存在 `build` script，则执行 `npm run build`
- 使用 PM2 启动或重启 `npm run start`
- 注入 `PORT` 环境变量
- 生成 Nginx 反向代理配置
- 校验 Nginx，reload
- `letsencrypt` 模式下申请证书并开启 HTTPS 跳转

示例：

```bash
sitectl create \
  --domain app.example.com \
  --type node \
  --root /srv/app \
  --port 3000 \
  --pm2-name app-example \
  --email ops@example.com
```

### `proxy`

适用于 Python / Go / Java / Docker 等已经在本地端口运行的服务。

必需参数：

- `--port`
- `--email`，仅 `letsencrypt` 模式需要

行为：

- 不负责启动应用
- 只生成 Nginx 反向代理配置
- 校验 Nginx，reload
- `letsencrypt` 模式下申请证书并开启 HTTPS 跳转

示例：

```bash
sitectl create \
  --domain api.example.com \
  --type proxy \
  --port 8080 \
  --email ops@example.com
```

### `static`

适用于 React / Vue / Vite 构建后的静态目录。

必需参数：

- `--root`
- `--email`，仅 `letsencrypt` 模式需要

行为：

- 校验静态目录是否存在
- 生成 Nginx 静态站点配置
- 默认启用 SPA 友好的 `try_files $uri $uri/ /index.html`
- 校验 Nginx，reload
- `letsencrypt` 模式下申请证书并开启 HTTPS 跳转

示例：

```bash
sitectl create \
  --domain www.example.com \
  --type static \
  --root /srv/www/example \
  --email ops@example.com
```

### `systemd`

适用于已经存在的 systemd 服务。

必需参数：

- `--port`
- `--service-name`
- `--email`，仅 `letsencrypt` 模式需要

行为：

- 不创建 systemd unit 文件
- 直接执行 `systemctl restart <service-name>`
- 生成 Nginx 反向代理配置
- 校验 Nginx，reload
- `letsencrypt` 模式下申请证书并开启 HTTPS 跳转

示例：

```bash
sitectl create \
  --domain svc.example.com \
  --type systemd \
  --port 9000 \
  --service-name my-backend \
  --email ops@example.com
```

## 证书模式

### `letsencrypt`

默认模式。

特点：

- 需要 `--email`
- 通过 Certbot 自动申请证书
- 自动启用 HTTPS 跳转
- 可以用 `sitectl renew` 续期

### `manual`

适用于 Cloudflare Origin CA、自签名证书、企业内部 CA 等。

必需参数：

- `--ssl-mode manual`
- `--ssl-cert`
- `--ssl-key`

特点：

- 不调用 Certbot
- 直接渲染带 `listen 443 ssl` 的 Nginx 配置
- 支持 `cert-info`、`cert-verify`、`cert-replace`
- 不支持 `sitectl renew`

示例：

```bash
sitectl create \
  --domain secure.example.com \
  --type proxy \
  --port 8443 \
  --ssl-mode manual \
  --ssl-cert /etc/ssl/certs/cloudflare-origin.pem \
  --ssl-key /etc/ssl/private/cloudflare-origin.key
```

## 命令详解

### `create`

创建站点。

通用参数：

- `--domain DOMAIN`
- `--type {node,proxy,static,systemd}`
- `--alias DOMAIN`，可重复使用
- `--ssl-mode {letsencrypt,manual}`
- `--ssl-cert PATH`
- `--ssl-key PATH`
- `--email EMAIL`
- `--force`
- `--dry-run`

示例：

```bash
sitectl create \
  --domain example.com \
  --type proxy \
  --port 8080 \
  --alias www.example.com \
  --alias api.example.com \
  --email ops@example.com
```

```bash
sitectl create \
  --domain secure.example.com \
  --type proxy \
  --port 8443 \
  --ssl-mode manual \
  --ssl-cert /etc/ssl/certs/origin.pem \
  --ssl-key /etc/ssl/private/origin.key
```

`--force` 行为：

- 如果目标 Nginx 配置已存在，会先备份旧配置
- 备份文件格式：`<domain>.bak.<timestamp>`
- 如果未加 `--force`，默认拒绝覆盖

### `update`

更新已有站点。

可修改字段：

- `--type`
- `--root`
- `--port`
- `--pm2-name`
- `--service-name`
- `--email`
- `--alias`
- `--clear-aliases`
- `--ssl-mode`
- `--ssl-cert`
- `--ssl-key`
- `--dry-run`

示例：

```bash
sitectl update api.example.com --port 9090 --email infra@example.com
```

```bash
sitectl update api.example.com --alias www.example.com --alias admin.example.com
```

```bash
sitectl update api.example.com --clear-aliases
```

```bash
sitectl update secure.example.com \
  --ssl-mode manual \
  --ssl-cert /etc/ssl/certs/new-origin.pem \
  --ssl-key /etc/ssl/private/new-origin.key
```

更新行为：

- 自动备份旧 Nginx 配置
- 重写配置并校验
- reload Nginx
- 更新状态文件
- 如果运行态失败，会尽量回滚 Nginx 和 PM2 / systemd

### `remove`

删除站点。

```bash
sitectl remove app.example.com
```

```bash
sitectl remove app.example.com --dry-run
```

行为：

- 删除 `sites-enabled` 软链
- 删除 `sites-available` 配置
- `node` 类型会尝试删除对应 PM2 进程
- `systemd` 类型会尝试停止对应服务
- 执行 `nginx -t` 和 reload
- 从状态文件移除站点

不会删除：

- Let's Encrypt 证书文件
- 手动证书文件
- 业务目录

### `list`

列出已管理站点。

```bash
sitectl list
```

行为：

- 优先从状态文件读取
- 如果状态文件缺失或损坏，会回退扫描 `sites-available`

### `status`

查看站点状态。

```bash
sitectl status app.example.com
```

输出至少包含：

- `domain`
- `type`
- `ssl_mode`
- Nginx 配置是否存在
- enabled 软链是否存在
- 证书文件是否存在
- `node` 类型时 PM2 进程是否存在
- `systemd` 类型时服务是否 active
- 本地端口是否可连接

### `reload`

校验并重载 Nginx。

```bash
sitectl reload
```

```bash
sitectl reload --dry-run
```

行为：

- 先执行 `nginx -t`
- 校验通过才执行 reload

### `renew`

续期 Let's Encrypt 证书。

```bash
sitectl renew
sitectl renew app.example.com
```

```bash
sitectl renew app.example.com --dry-run
```

说明：

- 无参数时执行全局续期
- 指定域名时执行 `certbot renew --cert-name DOMAIN`
- 续期后会执行 `nginx -t` 和 reload
- `manual` 站点不支持 `renew`

### `history`

列出站点备份历史。

```bash
sitectl history api.example.com
```

输出内容包括：

- 备份文件名
- 备份文件路径
- 是否附带状态元数据

### `rollback`

回滚站点到某个备份。

```bash
sitectl rollback api.example.com --backup api.example.com.bak.20260313153000123456
```

```bash
sitectl rollback api.example.com --backup 20260313153000123456 --dry-run
```

行为：

- 先备份当前配置
- 恢复目标 Nginx 配置
- 如果备份包含元数据，会恢复 `sites.json` 中的站点记录
- 会尝试恢复 PM2 或 systemd 运行态
- 执行 `nginx -t` 和 reload

### `export`

导出状态和配置。

```bash
sitectl export
```

```bash
sitectl export --output /tmp/sitectl-bundle.json
```

导出内容包括：

- 状态文件中的站点记录
- 每个站点当前 Nginx 配置

### `import`

从导出包恢复站点状态和配置。

```bash
sitectl import --input /tmp/sitectl-bundle.json
```

```bash
sitectl import --input /tmp/sitectl-bundle.json --force
```

```bash
sitectl import --input /tmp/sitectl-bundle.json --dry-run
```

行为：

- 恢复 `sites-available` 配置
- 恢复 `sites-enabled` 软链
- 合并状态文件
- 执行 `nginx -t` 和 reload

注意：

- 不会自动重建 PM2 进程
- 不会自动重启 systemd 服务
- 不会重新申请 Certbot 证书

### `logs`

查看日志。

```bash
sitectl logs app.example.com --error --lines 200
sitectl logs app.example.com --access --lines 50
sitectl logs app.example.com --pm2 --lines 100
sitectl logs svc.example.com --systemd --lines 100
```

说明：

- `--error` 读取 `/var/log/nginx/<domain>.error.log`
- `--access` 读取 `/var/log/nginx/<domain>.access.log`
- `--pm2` 读取 Node 站点 PM2 日志
- `--systemd` 读取 `journalctl` 日志
- 不传类型时默认查看 error log

### `healthcheck`

执行健康检查。

```bash
sitectl healthcheck app.example.com
```

```bash
sitectl healthcheck app.example.com --path /healthz --timeout 2
```

```bash
sitectl healthcheck app.example.com --skip-remote
```

默认会执行：

- 本地 TCP 检查 `127.0.0.1:<port>`
- 本地 HTTP 检查 `http://127.0.0.1:<port>/<path>`
- 远程 HTTPS 检查 `https://<domain>/<path>`

可选参数：

- `--path`
- `--timeout`
- `--skip-local`
- `--skip-remote`
- `--remote-url`

### `doctor`

环境自检。

```bash
sitectl doctor
```

如果你是在家里电脑或 NAS 上用公网 IPv6 提供服务，可以带上目标域名和计划中的站点参数一起检查：

```bash
sitectl doctor \
  --domain home.example.com \
  --type proxy \
  --port 8080 \
  --upstream-host ::1 \
  --listen-ipv6 \
  --email ops@example.com
```

检查项包括：

- `nginx`、`certbot`、`openssl`、`pm2`、`npm` 是否在 `PATH`
- `ip` 是否在 `PATH`
- `systemctl`、`journalctl` 是否在 `PATH`
- `sites-available` / `sites-enabled` 是否存在
- 状态文件父目录是否可写
- `nginx.conf` 是否包含 `sites-enabled`
- 80 / 443 端口是否可绑定
- IPv6 的 80 / 443 端口是否可绑定
- 是否检测到公网 IPv6 地址

如果检测到公网 IPv6，`doctor` 会额外提示：

- 可以把域名 AAAA 记录指向该 IPv6
- 可以为站点启用 `--listen-ipv6`
- 本地服务如果只监听 `::1`，可以配合 `--upstream-host ::1`
- 然后用 Let's Encrypt 或手动证书启用 HTTPS
- 如果传了 `--domain`，还会检查该域名的 AAAA 是否已经解析到本机 IPv6，并给出下一步 `sitectl create` 建议

### `cert-info`

查看证书详情。

```bash
sitectl cert-info secure.example.com
```

输出包括：

- `ssl_mode`
- `cert_path`
- `key_path`
- `exists`
- `subject`
- `issuer`
- `not_before`
- `not_after`
- `days_remaining`

### `cert-expiring`

列出即将过期或缺失的证书。

```bash
sitectl cert-expiring --days 14
```

行为：

- 列出在阈值内即将过期的证书
- 列出证书文件已缺失的站点

### `cert-warn`

适合定时任务或监控。

```bash
sitectl cert-warn --days 14
```

行为：

- 输出告警格式列表
- 如果存在即将过期或缺失的证书，退出码为 `1`
- 如果没有问题，退出码为 `0`

### `cert-verify`

检查证书和私钥是否匹配。

```bash
sitectl cert-verify secure.example.com
```

行为：

- 检查证书文件和私钥文件是否存在
- 使用 `openssl` 比较公钥
- 适用于 `letsencrypt` 和 `manual` 站点

### `cert-replace`

替换手动证书站点的证书文件。

```bash
sitectl cert-replace secure.example.com \
  --ssl-cert /etc/ssl/certs/rotated-origin.pem \
  --ssl-key /etc/ssl/private/rotated-origin.key
```

```bash
sitectl cert-replace secure.example.com \
  --ssl-cert /etc/ssl/certs/rotated-origin.pem \
  --ssl-key /etc/ssl/private/rotated-origin.key \
  --dry-run
```

行为：

- 仅适用于 `ssl_mode=manual`
- 更新状态文件中的证书路径
- 重写 Nginx 配置
- 自动执行 `nginx -t` 和 reload

## Alias 多域名

可以给一个站点配置多个 `server_name`。

```bash
sitectl create \
  --domain example.com \
  --type proxy \
  --port 8080 \
  --alias www.example.com \
  --alias api.example.com \
  --email ops@example.com
```

行为：

- Nginx `server_name` 会包含主域名和所有 alias
- Let's Encrypt 模式会为全部域名一起申请证书
- alias 会写入状态文件

## Dry Run

支持 `--dry-run` 的命令：

- `create`
- `update`
- `remove`
- `reload`
- `renew`
- `import`
- `rollback`
- `cert-replace`

Dry run 会输出：

- 将执行的操作
- 将写入的 Nginx 配置路径
- 渲染后的配置内容

不会真正写文件或执行系统命令。

## Nginx 模板行为

### `node` / `proxy` / `systemd`

生成的反向代理配置包含：

- `listen 80`
- `server_name`
- `access_log`
- `error_log`
- `proxy_pass http://127.0.0.1:<port>`
- `proxy_http_version 1.1`
- `proxy_set_header Host $host`
- `proxy_set_header X-Real-IP $remote_addr`
- `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for`
- `proxy_set_header X-Forwarded-Proto $scheme`
- `proxy_set_header Upgrade $http_upgrade`
- `proxy_set_header Connection "upgrade"`

### `static`

生成的静态配置包含：

- `listen 80`
- `server_name`
- `root <dir>`
- `index index.html`
- `try_files $uri $uri/ /index.html`

### 手动证书模式

手动证书模式会直接渲染 HTTPS server，包含：

- `listen 443 ssl`
- `ssl_certificate`
- `ssl_certificate_key`

## 状态文件

默认状态文件：

```text
/etc/sitectl/sites.json
```

示例：

```json
{
  "sites": [
    {
      "domain": "example.com",
      "type": "node",
      "ssl_mode": "letsencrypt",
      "aliases": [
        "www.example.com"
      ],
      "root": "/srv/app",
      "port": 3000,
      "pm2_name": "example-app",
      "service_name": null,
      "ssl_cert_path": null,
      "ssl_key_path": null,
      "email": "ops@example.com",
      "created_at": "2026-03-13T12:00:00+00:00"
    }
  ]
}
```

## 环境变量

这些环境变量可以覆盖默认路径，方便测试或自定义部署：

- `SITECTL_NGINX_AVAILABLE_DIR`
- `SITECTL_NGINX_ENABLED_DIR`
- `SITECTL_NGINX_MAIN_CONFIG`
- `SITECTL_STATE_FILE`
- `SITECTL_CERT_LIVE_DIR`
- `SITECTL_LOG_DIR`

## 默认路径

- `sites-available`: `/etc/nginx/sites-available`
- `sites-enabled`: `/etc/nginx/sites-enabled`
- `certbot live`: `/etc/letsencrypt/live`
- `state file`: `/etc/sitectl/sites.json`
- `nginx logs`: `/var/log/nginx`

## 测试

运行全部测试：

```bash
python3 -m unittest discover -s tests -v
```

## 注意事项

- `create` / `update` / `rollback` / `import` / `renew` / `cert-replace` 都会在真正 reload 前先执行 `nginx -t`
- 如果 `nginx -t` 失败，操作会停止并保留清晰错误信息
- `create` / `update` 在关键步骤失败时会尝试回滚 Nginx 配置和运行态
- `manual` 模式下请自行管理证书轮换
- `systemd` 类型目前管理的是已有服务，不会自动生成 unit 文件
