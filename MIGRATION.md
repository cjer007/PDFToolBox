# 换 VPS 与数据迁移指南

## 一、为什么客户端要连域名，不要连 IP

客户端里写死 IP（如 `43.128.119.89`）的后果：VPS 一换，所有已发布的客户端全部失联，
用户打开软件会提示"授权服务不可用"，付费用户也一样，等于软件作废。

连域名的做法：客户端永远连 `lic.cjers.top`，VPS 换了只改 DNS 的 A 记录，
客户端一行代码都不用改，用户也感觉不到。

**所以域名不是可选项，是必须项。**

---

## 二、首次配置（只需做一次）

Cloudflare → `cjers.top` → DNS → 记录 → 添加记录：

| 字段 | 值 |
|---|---|
| 类型 | A |
| 名称 | `lic` |
| IPv4 地址 | `43.128.119.89`（当前 VPS） |
| 代理状态 | **仅 DNS**（灰色云朵）← 先选这个 |
| TTL | 自动 |

保存后用以下命令确认：

```bash
nslookup lic.cjers.top
# 应返回 43.128.119.89
```

### 关于代理状态（灰云 vs 橙云）

| 模式 | 效果 | 建议 |
|---|---|---|
| **仅 DNS**（灰云） | 客户端直连 VPS，走 HTTP 明文 | **先用这个**，简单可靠 |
| 已代理（橙云） | 走 Cloudflare CDN，可上 HTTPS | 想要 HTTPS 时再切，需配 SSL/TLS 为「灵活」 |

灰云模式下客户端访问 `http://lic.cjers.top`；
橙云模式且 SSL 设为「灵活」时可用 `https://lic.cjers.top`（CF 到源站仍走 HTTP）。

客户端 `license.py` 里两种地址都列了，会按顺序自动选通的，所以切橙云不会影响老用户。

---

## 三、换 VPS 的完整步骤

### 准备（旧 VPS 上）

```bash
# 1. 备份数据库
sudo cp /home/ubuntu/lic/licenses.db /home/ubuntu/licenses_backup_$(date +%Y%m%d).db

# 2. 下载到本地
scp -i <密钥> ubuntu@旧IP:/home/ubuntu/licenses_backup_*.db .
```

数据库里保存了：所有用户的机器码、剩余试用次数、付费状态、兑换码。
**丢了等于所有付费用户白买。**

### 新 VPS 上部署

```bash
# 1. 装系统后先放行端口
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp

# 2. 上传文件
scp -i <密钥> server_stdlib.py ubuntu@新IP:/home/ubuntu/lic/
scp -i <密钥> licenses_backup_xxx.db ubuntu@新IP:/home/ubuntu/lic/licenses.db
scp -i <密钥> pdftool-lic.service ubuntu@新IP:/tmp/

# 3. 安装服务
sudo cp /tmp/pdftool-lic.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pdftool-lic

# 4. 验证
curl http://127.0.0.1/health
```

### 切换 DNS

Cloudflare 里把 `lic` 的 A 记录改成新 IP，保存。

**生效时间**：Cloudflare 通常 1-2 分钟。老客户端因为 DNS 有缓存，
最长可能要几小时才全部切过去。过渡期内旧 IP 的服务先别关。

### 过渡期做法

1. 旧 VPS 保留 1-2 周，直到确认没人再连它
2. 期间两台都能响应，数据以新机为准（旧机可以设为只读）
3. 观察旧机日志 `access.log` 没有新请求了，再关停

---

## 四、数据备份（已内置）

服务端每次被调用时会检查，**每天自动备份一次**到 `license_server/backups/`：

```
backups/licenses_20261113.db
backups/licenses_20261114.db
...
```

保留最近 30 份。导出到本地：

```bash
scp -i <密钥> -r ubuntu@43.128.119.89:/home/ubuntu/lic/backups/ ./lic_backups/
```

**建议每个月手动下载一次存到本地或网盘**，别只依赖服务器。

---

## 五、域名到期

`cjers.top` 的 `.top` 后缀首年便宜（几块钱），续费约 ¥30-40/年。
**记得设置自动续费**，域名过期比 VPS 过期更致命——VPS 换了能改 DNS，域名丢了所有用户全废。

---

## 六、如果哪天不想维护服务端了

有两条退路：

1. **一次性宣布所有存量机器码全部激活**，把数据库里的 `paid` 全设为 1，
   然后关停服务端。软件变成完全离线免费版，老用户不受影响。
2. **客户端加一个"最后通牒"版本**：联网失败超过 N 天就自动放开限制。
   （当前设计是断网 3 次后要求联网，可以改成永不放行或永久放行，看你的取舍）

第 1 条更干净。真到那一步，一条 SQL 就解决：

```sql
UPDATE licenses SET paid=1, trial_left=0;
```

---

## 七、检查清单

换机前逐项确认：

- [ ] 旧机 `licenses.db` 已下载到本地
- [ ] 新机服务已启动且 `curl 127.0.0.1/health` 正常
- [ ] 新机数据库文件权限正确（`ubuntu` 用户可写）
- [ ] Cloudflare A 记录已改
- [ ] 从外网 `curl http://lic.cjers.top/health` 通
- [ ] 用一台测试机的旧版本客户端能正常 checkin
- [ ] 旧机保留至少 1 周再做关停
