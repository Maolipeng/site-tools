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
- 通过环境感知的 `sites.json` 持久化本地状态，Linux 默认 `/etc/sitectl/sites.json`，macOS 默认 `~/Library/Application Support/sitectl/sites.json`

## 要求

- Python 3.11+
- Linux 服务器
- 已安装并可用的系统命令：
  - `nginx`
  - `certbot`
  - `openssl`
  - `pm2`、`npm`、`node`，仅 `node` 类型需要
  - `systemctl`、`journalctl`，仅 `systemd` 类型和部分运维命令需要

通常需要使用 `root` 或具备相应权限的用户执行，以便写入 Nginx 配置目录并重载 Nginx。Linux 默认状态文件在 `/etc/sitectl`，macOS 默认状态文件在当前用户目录下。

如果 `nginx` 不是安装在 `/etc/nginx`，`sitectl` 会自动探测常见布局：

- Linux 默认布局：`/etc/nginx/nginx.conf`
- Apple Silicon Homebrew：`/opt/homebrew/etc/nginx/nginx.conf`
- Intel Homebrew：`/usr/local/etc/nginx/nginx.conf`

探测成功后，会自动推导对应的 `sites-available`、`sites-enabled`、`snippets` 和日志目录。特殊环境仍然可以用环境变量显式覆盖。

## 安装

### 本地一键安装

```bash
cd /path/to/site-tools
./install.sh
```

默认行为：

- 创建本地虚拟环境 `.venv`
- 检测缺少的系统依赖，并尝试自动安装常见依赖（如 `nginx`、`certbot`、`openssl`、`node`、`npm`、`pm2`）
- 生成可直接运行的 `sitectl` 启动器
- 自动执行一次 `sitectl --help` smoke test

默认命令路径：

```bash
./.venv/bin/sitectl
```

常见变体：

```bash
./install.sh --user
./install.sh --system
./install.sh --venv /opt/sitectl-venv
./install.sh --no-editable
./install.sh --no-install-deps
```

说明：

- `--user` 和 `--system` 使用 `pip install`
- 默认 `venv` 模式更适合离线服务器

### `curl | bash` 安装

仓库内置了 bootstrap 脚本 [install.remote.sh](./install.remote.sh)。

通过仓库地址安装：

```bash
curl -fsSL https://raw.githubusercontent.com/Maolipeng/site-tools/main/install.remote.sh | bash
```

直接指定源码压缩包：

```bash
curl -fsSL https://raw.githubusercontent.com/Maolipeng/site-tools/main/install.remote.sh | \
  SITECTL_ARCHIVE_URL=https://github.com/Maolipeng/site-tools/archive/refs/heads/main.tar.gz bash
```

向内部安装脚本传参：

```bash
curl -fsSL https://raw.githubusercontent.com/Maolipeng/site-tools/main/install.remote.sh | \
  SITECTL_REPO_URL=https://github.com/Maolipeng/site-tools bash -s -- --user
```

### 传统安装

```bash
git clone https://github.com/Maolipeng/site-tools.git sitectl
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

仓库里已经附带了一个 skill，在 [skills/sitectl-ops/SKILL.md](./skills/sitectl-ops/SKILL.md)。

用途：

- 让大模型在触发 `sitectl` 运维场景时，优先按统一流程调用已有 CLI
- 自动把“先检查、再 dry-run、再执行、再验证”的流程固化下来
- 把 `create` / `update` / `status` / `logs` / `healthcheck` / `cert-*` / `rollback` 这些操作统一成一个 skill 能力

本地安装到 Codex skills 目录：

```bash
bash ./install-skill.sh
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
bash ./install-skill.sh --target claude
bash ./install-skill.sh --target opencode
bash ./install-skill.sh --target openclaw
bash ./install-skill.sh --target agents
bash ./install-skill.sh --target codex --target claude --target opencode --target openclaw
bash ./install-skill.sh --target all
```

默认全局安装目录：

- Codex: `~/.codex/skills` 或 `$CODEX_HOME/skills`
- Claude Code 兼容目录: `~/.claude/skills`
- OpenCode 全局目录: `${XDG_CONFIG_HOME:-~/.config}/opencode/skills`
- OpenClaw 全局目录: `~/.openclaw/skills`
- `.agents` 兼容目录: `~/.agents/skills`

也支持项目级安装：

```bash
bash ./install-skill.sh --target claude --scope project
bash ./install-skill.sh --target opencode --scope project
bash ./install-skill.sh --target openclaw --scope project
bash ./install-skill.sh --target agents --scope project
```

项目级目录分别是：

- Claude Code 兼容目录: `<project>/.claude/skills`
- OpenCode 项目目录: `<project>/.opencode/skills`
- OpenClaw 工作区目录: `<project>/skills`
- `.agents` 项目目录: `<project>/.agents/skills`

安装器还支持：

```bash
bash ./install-skill.sh --target opencode --mode copy
bash ./install-skill.sh --path /custom/skills
```

卸载：

```bash
bash ./uninstall-skill.sh
```

也支持按 target 卸载：

```bash
bash ./uninstall-skill.sh --target claude
bash ./uninstall-skill.sh --target opencode
bash ./uninstall-skill.sh --target openclaw
bash ./uninstall-skill.sh --target all
```

skill 内还附带了一组稳定脚本，适合被模型直接调用：

```bash
python3 ./skills/sitectl-ops/scripts/site_json.py list
python3 ./skills/sitectl-ops/scripts/site_json.py status app.example.com
python3 ./skills/sitectl-ops/scripts/site_json.py export --output /tmp/sitectl-bundle.json
python3 ./skills/sitectl-ops/scripts/site_json.py logs app.example.com --kind error --lines 200
python3 ./skills/sitectl-ops/scripts/site_json.py cert-warn --days 14
python3 ./skills/sitectl-ops/scripts/site_json.py preview-update app.example.com --port 9090
python3 ./skills/sitectl-ops/scripts/site_json.py apply-reload
python3 ./skills/sitectl-ops/scripts/site_json.py preview-import --input /tmp/sitectl-bundle.json --force
python3 ./skills/sitectl-ops/scripts/site_json.py apply-rollback app.example.com --backup 20260313153000123456
python3 ./skills/sitectl-ops/scripts/site_json.py apply-history app.example.com
python3 ./skills/sitectl-ops/scripts/site_audit.py app.example.com --include-runtime-log
python3 ./skills/sitectl-ops/scripts/site_cert_report.py --days 14
python3 ./skills/sitectl-ops/scripts/site_fleet_audit.py --include-runtime-log --only-problems
python3 ./skills/sitectl-ops/scripts/site_fleet_autofix.py --only-problems --max-priority medium --dry-run-before-apply
python3 ./skills/sitectl-ops/scripts/site_automation_templates.py --format json
python3 ./skills/sitectl-ops/scripts/site_automation_templates.py --format directives --template daily-fleet-audit
bash ./skills/sitectl-ops/scripts/site_status.sh app.example.com
bash ./skills/sitectl-ops/scripts/site_healthcheck.sh app.example.com --path /healthz
bash ./skills/sitectl-ops/scripts/site_cert_verify.sh secure.example.com
bash ./skills/sitectl-ops/scripts/site_safe_create.sh --domain api.example.com --type proxy --port 8080 --email ops@example.com --apply
bash ./skills/sitectl-ops/scripts/site_safe_update.sh api.example.com --port 9090 --apply
bash ./skills/sitectl-ops/scripts/site_safe_remove.sh api.example.com --apply
```

这些脚本会自动尝试：

- 直接调用 `sitectl`
- 调用仓库 `.venv/bin/sitectl`
- 回退到 `PYTHONPATH=. python3 -m sitectl`

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
- `site_fleet_autofix.py` 会读取 [autofix-policy.json](./skills/sitectl-ops/assets/autofix-policy.json) 策略文件，支持命令白名单、黑名单、域名限制和按命令规则覆盖
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

## 部署示例

下面每种部署都给一套可直接参考的流程，覆盖创建、检查和常见更新动作。

### Node / PM2 部署示例

适合 Next.js、Express、NestJS、Koa 等 Node 项目。

```bash
sitectl create \
  --domain app.example.com \
  --type node \
  --root /srv/app \
  --port 3000 \
  --pm2-name app-example \
  --email ops@example.com

sitectl status app.example.com
sitectl healthcheck app.example.com --path /healthz
sitectl logs app.example.com --pm2 --lines 100
sitectl update app.example.com --port 3001
```

### 反向代理部署示例

适合已经在本地端口运行的 Python、Go、Java、Docker 服务。

```bash
sitectl create \
  --domain api.example.com \
  --type proxy \
  --port 8080 \
  --email ops@example.com

sitectl status api.example.com
sitectl healthcheck api.example.com --path /ready
sitectl logs api.example.com --error --lines 100
sitectl update api.example.com --port 9090
```

### 静态站点部署示例

适合 React、Vue、Vite、Astro 等构建后的产物目录。

```bash
sitectl create \
  --domain www.example.com \
  --type static \
  --root /srv/www/example \
  --email ops@example.com

sitectl status www.example.com
sitectl healthcheck www.example.com
sitectl update www.example.com --alias cdn.example.com
```

### systemd 服务部署示例

适合已经存在 unit 的后端服务。

```bash
sitectl create \
  --domain svc.example.com \
  --type systemd \
  --port 9000 \
  --service-name my-backend \
  --email ops@example.com

sitectl status svc.example.com
sitectl logs svc.example.com --systemd --lines 100
sitectl update svc.example.com --service-name my-backend-v2 --port 9100
```

### IPv6 代理部署示例

适合家庭宽带、NAS 或仅监听 `::1` 的本地服务。

```bash
sitectl doctor \
  --domain ipv6.example.com \
  --type proxy \
  --port 8080 \
  --upstream-host ::1 \
  --listen-ipv6 \
  --email ops@example.com

sitectl create \
  --domain ipv6.example.com \
  --type proxy \
  --port 8080 \
  --upstream-host ::1 \
  --listen-ipv6 \
  --email ops@example.com

sitectl healthcheck ipv6.example.com
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
- 优先按 `packageManager` 字段或锁文件自动选择 `pnpm`、`yarn`、`npm`
- 执行对应的 `<package-manager> install`
- 如果存在 `build` script，则执行对应的 `<package-manager> run build`
- 使用 PM2 启动或重启对应的 `<package-manager> run start`
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

用途：创建一个新的受管站点，并按站点类型生成 Nginx 配置、维护状态文件，必要时处理运行态和证书。

关键参数：

- `--domain DOMAIN`，主域名
- `--type {node,proxy,static,systemd}`，站点类型
- `--root PATH`，`node` 和 `static` 常用
- `--port PORT`，`node`、`proxy`、`systemd` 必需
- `--pm2-name NAME`，`node` 必需
- `--service-name NAME`，`systemd` 必需
- `--alias DOMAIN`，可重复传入多个别名
- `--listen-ipv6`，生成显式 IPv6 `listen`
- `--upstream-host HOST`，指定回源地址，如 `127.0.0.1` 或 `::1`
- `--ssl-mode {letsencrypt,manual}`，默认为 `letsencrypt`
- `--ssl-cert PATH` 和 `--ssl-key PATH`，`manual` 模式必需
- `--email EMAIL`，`letsencrypt` 模式必需
- `--force`，允许覆盖已有配置
- `--dry-run`，只预览不落地

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

补充说明：

- `--force` 会先备份旧配置，备份名格式为 `<domain>.bak.<timestamp>`
- 未加 `--force` 时，遇到同名配置默认拒绝覆盖

### `update`

用途：更新已有站点配置，并在必要时重写 Nginx、切换证书参数、调整 PM2 或 systemd 关联设置。

关键参数：

- `domain`，要更新的站点域名
- `--type`、`--root`、`--port`
- `--pm2-name`、`--service-name`
- `--listen-ipv6`、`--no-listen-ipv6`
- `--upstream-host`
- `--alias`、`--clear-aliases`
- `--ssl-mode`、`--ssl-cert`、`--ssl-key`
- `--email`
- `--dry-run`

示例：

```bash
sitectl update api.example.com --port 9090 --email infra@example.com
```

```bash
sitectl update api.example.com --alias www.example.com --alias admin.example.com
```

```bash
sitectl update api.example.com --clear-aliases --listen-ipv6 --upstream-host ::1
```

```bash
sitectl update secure.example.com \
  --ssl-mode manual \
  --ssl-cert /etc/ssl/certs/new-origin.pem \
  --ssl-key /etc/ssl/private/new-origin.key
```

补充说明：

- 更新前会备份旧配置
- 修改失败时会尽量回滚 Nginx 和运行态

### `remove`

用途：移除站点配置和受管状态。

关键参数：

- `domain`
- `--dry-run`

示例：

```bash
sitectl remove app.example.com
```

```bash
sitectl remove app.example.com --dry-run
```

补充说明：

- 会删除 `sites-enabled` 软链和 `sites-available` 配置
- `node` 会尝试删除 PM2 进程，`systemd` 会尝试停止服务
- 不会删除业务目录、Let's Encrypt 证书文件或手动证书文件

### `list`

用途：列出当前所有受管站点。

示例：

```bash
sitectl list
```

补充说明：

- 优先读取状态文件
- 状态文件损坏时会回退扫描 Nginx 配置目录

### `status`

用途：查看单个站点的配置、证书和运行状态。

关键参数：

- `domain`

示例：

```bash
sitectl status app.example.com
```

输出通常包含：

- 站点基础信息：`domain`、`type`、`ssl_mode`
- Nginx 配置和 enabled 软链是否存在
- 证书文件是否存在
- 本地端口是否可连通
- `node` 站点的 PM2 状态
- `systemd` 站点的服务状态

### `reload`

用途：执行 `nginx -t` 校验并重载 Nginx。

关键参数：

- `--dry-run`

示例：

```bash
sitectl reload
```

```bash
sitectl reload --dry-run
```

### `renew`

用途：续期 Let's Encrypt 证书。

关键参数：

- `domain`，可选；不传时续期全部
- `--dry-run`

示例：

```bash
sitectl renew
sitectl renew app.example.com
```

```bash
sitectl renew app.example.com --dry-run
```

补充说明：

- 指定域名时等价于按 `cert-name` 续期
- 续期后会重新校验并 reload Nginx
- `manual` 证书站点不支持该命令

### `history`

用途：查看某个站点可用的备份历史。

关键参数：

- `domain`

示例：

```bash
sitectl history api.example.com
```

输出通常包含：

- 备份文件名
- 备份路径
- 是否包含站点元数据

### `rollback`

用途：从备份恢复某个站点。

关键参数：

- `domain`
- `--backup BACKUP`
- `--dry-run`

示例：

```bash
sitectl rollback api.example.com --backup api.example.com.bak.20260313153000123456
```

```bash
sitectl rollback api.example.com --backup 20260313153000123456 --dry-run
```

补充说明：

- 会先备份当前配置，再恢复目标备份
- 备份若带元数据，会同时恢复状态文件记录

### `export`

用途：导出站点状态和当前配置，便于迁移或备份。

关键参数：

- `--output FILE`

示例：

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

用途：从导出包导入受管站点配置。

关键参数：

- `--input FILE`
- `--force`
- `--dry-run`

示例：

```bash
sitectl import --input /tmp/sitectl-bundle.json
```

```bash
sitectl import --input /tmp/sitectl-bundle.json --force --dry-run
```

补充说明：

- 会恢复 Nginx 配置、软链和状态文件记录
- 不会自动重建 PM2 进程、重启 systemd 服务或重新签发证书

### `logs`

用途：查看站点相关日志。

关键参数：

- `domain`
- `--access`、`--error`、`--pm2`、`--systemd`
- `--lines N`

示例：

```bash
sitectl logs app.example.com --error --lines 200
sitectl logs app.example.com --access --lines 50
sitectl logs app.example.com --pm2 --lines 100
sitectl logs svc.example.com --systemd --lines 100
```

补充说明：

- 不传类型时默认读取 Nginx error log
- `--pm2` 仅适合 `node` 站点
- `--systemd` 仅适合 `systemd` 站点

### `healthcheck`

用途：对站点执行本地和远程健康检查。

关键参数：

- `domain`
- `--path PATH`
- `--timeout SECONDS`
- `--skip-local`
- `--skip-remote`
- `--remote-url URL`

示例：

```bash
sitectl healthcheck app.example.com
```

```bash
sitectl healthcheck app.example.com --path /healthz --timeout 2
```

```bash
sitectl healthcheck app.example.com --skip-remote
```

默认检查包括：

- 本地 TCP 连接检查
- 本地 HTTP 探测
- 远程 HTTPS 探测

### `doctor`

用途：检查当前环境是否适合部署站点，特别适合上线前排查 Nginx、证书和 IPv6 准备情况。

关键参数：

- `--domain`
- `--type`
- `--port`
- `--upstream-host`
- `--listen-ipv6`
- `--email`
- `--ssl-mode {letsencrypt,manual}`

示例：

```bash
sitectl doctor
```

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

- 核心命令是否在 `PATH`
- 当前 Nginx 主配置和派生目录是否可用
- 状态目录是否可写
- 80 和 443 端口是否可绑定
- IPv6 是否可用以及是否检测到公网 IPv6
- 如果传了 `--domain`，还会检查该域名的 AAAA 解析和下一步建议

### `cert-info`

用途：查看某个站点当前证书的详细信息。

关键参数：

- `domain`

示例：

```bash
sitectl cert-info secure.example.com
```

输出通常包含：

- 证书路径和私钥路径
- `subject`、`issuer`
- `not_before`、`not_after`
- 剩余有效天数

### `cert-expiring`

用途：列出即将过期或已缺失的证书。

关键参数：

- `--days N`，默认 `30`

示例：

```bash
sitectl cert-expiring --days 14
```

### `cert-warn`

用途：用于 cron 或监控系统的证书告警命令。

关键参数：

- `--days N`，默认 `30`

示例：

```bash
sitectl cert-warn --days 14
```

补充说明：

- 有问题时退出码为 `1`
- 无问题时退出码为 `0`

### `cert-verify`

用途：检查证书文件与私钥是否匹配。

关键参数：

- `domain`

示例：

```bash
sitectl cert-verify secure.example.com
```

补充说明：

- 同时适用于 `letsencrypt` 和 `manual` 站点
- 底层通过 `openssl` 对比公钥

### `cert-replace`

用途：替换手动证书站点使用的证书文件。

关键参数：

- `domain`
- `--ssl-cert PATH`
- `--ssl-key PATH`
- `--dry-run`

示例：

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

补充说明：

- 仅适用于 `ssl_mode=manual`
- 替换后会重写配置并 reload Nginx

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
Linux 默认：

```bash
/etc/sitectl/sites.json
```

macOS 默认：

```bash
~/Library/Application\ Support/sitectl/sites.json
```
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
- `SITECTL_NGINX_SNIPPETS_DIR`
- `SITECTL_NGINX_MAIN_CONFIG`
- `SITECTL_STATE_FILE`
- `SITECTL_CERT_LIVE_DIR`
- `SITECTL_LOG_DIR`

## 默认路径

- 默认会先自动探测 `nginx.conf`，支持：
  - `/etc/nginx/nginx.conf`
  - `/opt/homebrew/etc/nginx/nginx.conf`
  - `/usr/local/etc/nginx/nginx.conf`
- `sites-available`: `<nginx.conf 所在目录>/sites-available`
- `sites-enabled`: `<nginx.conf 所在目录>/sites-enabled`
- `snippets`: `<nginx.conf 所在目录>/snippets`
- `certbot live`: `/etc/letsencrypt/live`
- `state file`: Linux 默认 `/etc/sitectl/sites.json`，macOS 默认 `~/Library/Application Support/sitectl/sites.json`
- `nginx logs`: Linux 默认 `/var/log/nginx`，Homebrew 默认 `<prefix>/var/log/nginx`

## 测试

运行全部测试：

```bash
python3 -m unittest discover -s tests -v
```

## 在 macOS 上切换 443 给 nginx 或 Tailscale

如果你本机同时装了 Homebrew nginx 和 Tailscale，而 `443` 只能由其中一个进程占用，可以用仓库里这两个脚本切换：

```bash
zsh /Users/maolipeng/site-tools/scripts/switch_443_to_nginx.sh
zsh /Users/maolipeng/site-tools/scripts/switch_443_to_tailscale.sh
```

说明：

- `switch_443_to_nginx.sh` 会退出 Tailscale，然后重启 Homebrew nginx
- `switch_443_to_tailscale.sh` 会停止 Homebrew nginx，然后重新打开 Tailscale
- 两个脚本最后都会打印当前 `:443` 的监听者，方便确认是否切换成功
- 如果 Tailscale 不是通过 GUI app 接管 `443`，你需要按自己的 Tailscale 用法补充额外启动步骤

## 注意事项

- `create` / `update` / `rollback` / `import` / `renew` / `cert-replace` 都会在真正 reload 前先执行 `nginx -t`
- 如果 `nginx -t` 失败，操作会停止并保留清晰错误信息
- `create` / `update` 在关键步骤失败时会尝试回滚 Nginx 配置和运行态
- `manual` 模式下请自行管理证书轮换
- `systemd` 类型目前管理的是已有服务，不会自动生成 unit 文件
