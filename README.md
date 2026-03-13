# sitectl

`sitectl` 是一个轻量级 Linux 服务器站点管理 CLI，用于快速创建和维护 Nginx 站点、Let's Encrypt 证书以及 Node/Next.js 项目的 PM2 进程。

## 功能

- 自动生成 Nginx 配置
- 支持 `node`、`proxy`、`static`、`systemd` 四类站点
- 使用 Certbot 申请与续期 Let's Encrypt 证书
- 支持接入手动证书，例如 Cloudflare Origin CA 或其他已生成好的证书
- 为 Node 项目执行 `npm install`、可选 `npm run build`、并通过 PM2 启动
- 支持通过 `systemctl` 管理已有的 systemd 服务
- 列出站点、删除站点、查看状态、重载 Nginx
- 支持本地端口、HTTP 和远程 HTTPS 健康检查
- 通过 `/etc/sitectl/sites.json` 维护本地状态

## 要求

- Python 3.11+
- Linux 服务器
- 已安装并可用的系统命令：
  - `nginx`
  - `certbot`
  - `pm2`（仅 `node` 类型需要）
  - `npm` / `node`（仅 `node` 类型需要）
  - `systemctl` / `journalctl`（`systemd` 类型和日志查看需要）

通常需要使用 `root` 或具备相应权限的用户执行，以便写入 `/etc/nginx`、`/etc/sitectl` 并重载 Nginx。

## 安装

一键安装脚本：

```bash
cd /Users/maolipeng/Documents/selfProject/site-tools
./install.sh
```

如果要做成 `curl | bash` 风格，仓库里也提供了 bootstrap 脚本 [install.remote.sh](/Users/maolipeng/Documents/selfProject/site-tools/install.remote.sh)。

示例：

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.remote.sh | \
  SITECTL_REPO_URL=https://github.com/<owner>/<repo> bash
```

或者直接指定源码压缩包：

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.remote.sh | \
  SITECTL_ARCHIVE_URL=https://github.com/<owner>/<repo>/archive/refs/heads/main.tar.gz bash
```

给内部安装脚本传参：

```bash
curl -fsSL https://raw.githubusercontent.com/<owner>/<repo>/main/install.remote.sh | \
  SITECTL_REPO_URL=https://github.com/<owner>/<repo> bash -s -- --user
```

默认行为：

- 创建本地虚拟环境 `.venv`
- 以本地 launcher 方式安装当前项目，默认不依赖联网下载构建依赖
- 自动执行一次 `sitectl --help` smoke test

脚本会在结束时输出可执行命令路径，默认是：

```bash
/Users/maolipeng/Documents/selfProject/site-tools/.venv/bin/sitectl
```

可选安装方式：

```bash
./install.sh --user
./install.sh --system
./install.sh --venv /opt/sitectl-venv
./install.sh --no-editable
```

说明：

- `--user` 和 `--system` 使用 `pip install`
- 默认 `venv` 模式更适合离线服务器

```bash
git clone <your-repo-url> sitectl
cd sitectl
python3.11 -m venv .venv
source .venv/bin/activate
pip install .
```

开发环境可直接运行：

```bash
python -m sitectl.cli --help
```

## 命令

```bash
sitectl create --domain DOMAIN --type TYPE [options]
sitectl update DOMAIN [options]
sitectl remove DOMAIN
sitectl list
sitectl history DOMAIN
sitectl rollback DOMAIN --backup BACKUP [--dry-run]
sitectl export [--output FILE]
sitectl import --input FILE [--force] [--dry-run]
sitectl cert-info DOMAIN
sitectl cert-expiring [--days N]
sitectl cert-warn [--days N]
sitectl cert-verify DOMAIN
sitectl cert-replace DOMAIN --ssl-cert PATH --ssl-key PATH [--dry-run]
sitectl logs DOMAIN [--access|--error|--pm2] [--lines N]
sitectl status DOMAIN
sitectl healthcheck DOMAIN [--path PATH]
sitectl doctor
sitectl reload
sitectl renew [DOMAIN]
```

## 使用示例

### 1. 创建 Node/Next.js 站点

```bash
sitectl create \
  --domain app.example.com \
  --type node \
  --root /srv/app \
  --port 3000 \
  --pm2-name app-example \
  --email ops@example.com
```

行为：

- 校验 `/srv/app/package.json`
- 执行 `npm install`
- 如果存在 `build` script，则执行 `npm run build`
- 使用 PM2 启动 `npm run start`
- 生成 Nginx 反向代理配置
- 运行 `nginx -t` 和 reload
- 通过 Certbot 申请证书并开启 HTTPS 跳转

### 2. 创建反向代理站点

```bash
sitectl create \
  --domain api.example.com \
  --type proxy \
  --port 8080 \
  --email ops@example.com
```

### 3. 创建静态站点

```bash
sitectl create \
  --domain www.example.com \
  --type static \
  --root /srv/www/example \
  --email ops@example.com
```

### 4. 创建 systemd 站点

```bash
sitectl create \
  --domain svc.example.com \
  --type systemd \
  --port 9000 \
  --service-name my-backend \
  --email ops@example.com
```

行为：

- 不创建 systemd unit 文件，要求服务已存在
- 执行 `systemctl restart my-backend`
- 生成 Nginx 反向代理配置
- 运行 `nginx -t` 和 reload
- 通过 Certbot 申请证书并开启 HTTPS 跳转

### 5. 覆盖已有配置

```bash
sitectl create \
  --domain app.example.com \
  --type proxy \
  --port 4000 \
  --email ops@example.com \
  --force
```

覆盖时会先备份旧配置为：

```text
/etc/nginx/sites-available/app.example.com.bak.<timestamp>
```

### 6. 查看站点列表和状态

```bash
sitectl list
sitectl status app.example.com
```

`status` 现在会额外输出：

- `pm2_process_exists`
- `systemd_service_active`
- `port_open`

### 7. 更新已有站点

```bash
sitectl update api.example.com --port 9090 --email infra@example.com
sitectl update api.example.com --alias www.example.com --alias admin.example.com
sitectl update api.example.com --clear-aliases
```

更新命令会：

- 读取状态文件中的已有站点配置
- 合并你提供的新参数
- 自动备份旧 Nginx 配置
- 重写配置并重新校验、reload
- 成功后更新状态文件

`systemd` 类型更新示例：

```bash
sitectl update svc.example.com --port 9100 --service-name my-backend-v2
```

### 8. 多域名 alias

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

- Nginx `server_name` 会渲染为 `example.com www.example.com api.example.com`
- Certbot 会对主域名和所有 alias 一次性申请证书
- alias 会持久化到 `sites.json`

### 9. 手动证书 / Cloudflare Origin CA

```bash
sitectl create \
  --domain secure.example.com \
  --type proxy \
  --port 8443 \
  --ssl-mode manual \
  --ssl-cert /etc/ssl/certs/cloudflare-origin.pem \
  --ssl-key /etc/ssl/private/cloudflare-origin.key
```

说明：

- `--ssl-mode letsencrypt` 是默认值
- `--ssl-mode manual` 时不会调用 Certbot
- 会直接渲染 `listen 443 ssl` 的 Nginx 配置
- 要求 `--ssl-cert` 和 `--ssl-key` 指向已存在的文件
- 适用于 Cloudflare Origin CA、自签名证书、企业内部 CA 等场景

更新已有站点证书来源：

```bash
sitectl update secure.example.com \
  --ssl-mode manual \
  --ssl-cert /etc/ssl/certs/new-origin.pem \
  --ssl-key /etc/ssl/private/new-origin.key
```

### 10. 证书检查

```bash
sitectl cert-info secure.example.com
sitectl cert-expiring --days 14
sitectl cert-warn --days 14
sitectl cert-verify secure.example.com
```

`cert-info` 会输出：

- `ssl_mode`
- 当前证书路径和私钥路径
- 是否存在
- subject / issuer
- 生效时间和过期时间
- 剩余天数

`cert-expiring` 会列出：

- 即将在指定天数内过期的证书
- 或者证书文件已经缺失的站点

`cert-warn` 用于告警或定时任务：

- 输出格式和 `cert-expiring` 类似
- 如果存在即将过期或已缺失的证书，会返回退出码 `1`
- 如果一切正常，会返回退出码 `0`

`cert-verify` 会检查：

- 证书文件和私钥文件是否都存在
- 证书公钥和私钥公钥是否匹配
- 适用于 Let’s Encrypt 和手动证书站点

替换手动证书：

```bash
sitectl cert-replace secure.example.com \
  --ssl-cert /etc/ssl/certs/rotated-origin.pem \
  --ssl-key /etc/ssl/private/rotated-origin.key
```

行为：

- 仅适用于 `ssl_mode=manual` 的站点
- 会更新状态文件中的证书路径
- 会重写 Nginx 配置
- 自动执行 `nginx -t` 和 reload
- 支持 `--dry-run`

### 11. Dry Run 预览

```bash
sitectl create \
  --domain app.example.com \
  --type node \
  --root /srv/app \
  --port 3000 \
  --pm2-name app-example \
  --email ops@example.com \
  --dry-run
```

支持 `--dry-run` 的命令：

- `create`
- `update`
- `cert-replace`
- `remove`
- `reload`
- `renew`

Dry run 会输出：

- 将执行的系统命令
- 将写入的 Nginx 配置路径
- 渲染后的配置内容
- 将修改的状态文件

不会真正写文件或执行系统命令。

### 12. 导出和导入

```bash
sitectl export --output /tmp/sitectl-bundle.json
sitectl import --input /tmp/sitectl-bundle.json --dry-run
sitectl import --input /tmp/sitectl-bundle.json --force
```

导出内容包括：

- 状态文件里的所有站点记录
- 每个站点当前的 Nginx 配置内容
- 手动证书模式的配置字段和证书路径

导入行为：

- 恢复 `sites-available` 配置
- 恢复 `sites-enabled` 软链
- 合并站点状态到本地 `sites.json`
- 执行 `nginx -t` 和 reload

注意：

- `import` 不会自动重建 PM2 进程
- `import` 不会自动 `systemctl restart`
- `import` 不会重新申请 Certbot 证书

### 13. 备份历史和回滚

```bash
sitectl history api.example.com
sitectl rollback api.example.com --backup api.example.com.bak.20260313153000123456
sitectl rollback api.example.com --backup 20260313153000123456 --dry-run
```

行为：

- `history` 列出该站点已有的 Nginx 备份
- 每个备份会标记是否包含状态元数据
- `rollback` 会先备份当前配置，再恢复指定备份
- 如果备份有元数据，会一并恢复 `sites.json` 里的站点记录
- 如果备份记录的是 `node` 站点，会尝试恢复对应 PM2 进程
- 如果备份记录的是 `systemd` 站点，会尝试恢复对应 systemd service
- 如果当前版本有不再匹配的 PM2 进程或 systemd service，会先清理当前运行态
- 回滚完成后会执行 `nginx -t` 和 reload

注意：

- `node` 回滚依赖原项目目录仍然存在且可启动
- `systemd` 回滚依赖旧 service 名称在系统中仍可用

### 14. 续期证书

```bash
sitectl renew
sitectl renew app.example.com
```

说明：

- `letsencrypt` 站点支持 `renew`
- `manual` 站点不会通过 Certbot 续期，需自行替换证书文件后执行 `sitectl reload`

### 15. 查看日志

```bash
sitectl logs app.example.com --error --lines 200
sitectl logs app.example.com --access --lines 50
sitectl logs app.example.com --pm2 --lines 100
sitectl logs svc.example.com --systemd --lines 100
```

说明：

- `--error` 读取 `/var/log/nginx/<domain>.error.log`
- `--access` 读取 `/var/log/nginx/<domain>.access.log`
- `--pm2` 对 `node` 类型站点执行 `pm2 logs <name> --nostream`
- `--systemd` 对 `systemd` 类型站点执行 `journalctl -u <service> -n <lines> --no-pager`
- 不传类型时默认查看 error log

### 16. 健康检查

```bash
sitectl healthcheck app.example.com
sitectl healthcheck app.example.com --path /healthz
sitectl healthcheck app.example.com --skip-remote
```

默认会执行：

- 本地 TCP 检查 `127.0.0.1:<port>`
- 本地 HTTP 检查 `http://127.0.0.1:<port>/<path>`
- 远程 HTTPS 检查 `https://<domain>/<path>`

可选参数：

- `--path` 指定检查路径
- `--timeout` 指定超时秒数
- `--skip-local` 跳过本地检查
- `--skip-remote` 跳过远程检查
- `--remote-url` 覆盖远程 URL，适合测试环境

### 17. 环境自检

```bash
sitectl doctor
```

会检查：

- `nginx`、`certbot`、`pm2`、`npm` 是否在 `PATH`
- `systemctl`、`journalctl` 是否在 `PATH`
- `sites-available` / `sites-enabled` 是否存在
- 状态文件父目录是否可写
- `nginx.conf` 是否包含 `sites-enabled`
- 80 / 443 端口是否可绑定

## 状态文件

默认状态文件路径：

```text
/etc/sitectl/sites.json
```

结构示例：

```json
{
  "sites": [
    {
      "domain": "example.com",
      "type": "node",
      "root": "/srv/app",
      "port": 3000,
      "pm2_name": "example-app",
      "email": "ops@example.com",
      "created_at": "2026-03-13T12:00:00+00:00"
    }
  ]
}
```

## 环境变量

以下环境变量可用于覆盖默认路径，方便测试或自定义部署：

- `SITECTL_NGINX_AVAILABLE_DIR`
- `SITECTL_NGINX_ENABLED_DIR`
- `SITECTL_NGINX_MAIN_CONFIG`
- `SITECTL_STATE_FILE`
- `SITECTL_CERT_LIVE_DIR`
- `SITECTL_LOG_DIR`

## 删除说明

`sitectl remove DOMAIN` 会：

- 删除 `sites-enabled` 软链
- 删除 `sites-available` 配置文件
- Node 站点时尝试删除对应 PM2 进程
- systemd 站点时尝试停止对应 service
- 执行 `nginx -t` 和 reload
- 从状态文件中移除记录

不会删除：

- Let's Encrypt 证书文件
- 项目目录或静态资源目录

## 测试

```bash
python -m unittest discover -s tests -v
```

## 常见问题

### `nginx -t` 失败

工具会中止 reload 并直接输出 Nginx 的 stderr/stdout，便于定位配置错误。

### Certbot 失败

工具不会吞掉错误；会把 Certbot 的输出作为异常信息返回。

### 自动回滚

`create` 和 `update` 在以下步骤失败时会尽力自动回滚：

- 写入新 Nginx 配置后 `nginx -t` 失败
- reload 失败
- Certbot 申请证书失败

回滚内容包括：

- 恢复原来的 Nginx 配置和 enabled 软链
- 对新创建的 PM2 进程执行清理
- 对被重启覆盖的旧 PM2 进程尝试恢复

### PM2 进程不存在

删除站点时，如果 PM2 进程不存在，会打印警告但不会阻塞站点移除流程。
