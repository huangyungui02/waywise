# 账号和登录

账号使用用户名和密码，PyJWT 签发 HS256 JWT，pwdlib 使用 Argon2 哈希密码。服务端 `JWT_SECRET_KEY` 至少 32 个字符，使用 `openssl rand -hex 32` 生成，不传入前端。更换签名密钥会使旧令牌失效。

- `POST /api/auth/login`：JSON `username`、`password`，返回 `access_token`、`refresh_token` 和 `token_type`。
- `POST /api/auth/refresh`：JSON `refresh_token`，返回新的令牌对；旧 refresh token 失效。
- `GET /api/auth/me`：使用 access token 返回用户 ID 和用户名。
- `POST /api/auth/logout`：使用 access token，撤销当前登录会话。
- `POST /api/auth/change-password`：使用 access token，JSON `old_password`、`new_password`，撤销全部登录会话，需重新登录。

access token 有效期 15 分钟。每次登录创建一条 `auth_sessions`，最终到期时间为登录后 30 天，刷新不延长最终期限。数据库仅保存当前 refresh token 的 SHA-256 摘要。两个令牌携带用户 `sub` 和会话 `sid`，接口严格区分令牌类型。

刷新时按用户、登录会话顺序加行锁，校验当前摘要并原子轮换。旧令牌重用返回 401。客户端合并同一页面内的并发刷新，业务请求认证失败最多刷新重试一次。浏览器使用单个标签页；当前未实现跨标签页的刷新协调。

业务请求校验 JWT 后，查询有效登录会话和启用的用户；退出、改密和停用用户立即生效。聊天会话通过 `user_id` 归属用户，商品、方案与工作流操作均先检查会话归属。已提交的后台回复不因退出而取消。

iOS refresh token 保存在 Keychain；access token 只保存在内存。网页 refresh token 保存在 localStorage。IndexedDB 聊天缓存按用户分库，旧的无归属缓存不再读取。

在 `.env` 中配置必填的 `INITIAL_USERNAME` 和 `INITIAL_PASSWORD`，后端启动时自动创建初始用户。用户名沿用登录校验并统一转小写，密码为 8 至 128 个字符；数据库只保存 Argon2 哈希。已有同名用户时跳过，不覆盖密码或启用状态；页面改密后重启不会重置密码。更换初始用户名会创建另一个用户，不转移原有数据。暂不提供公开注册、密码找回、角色管理或设备列表。公网部署应在入口设置登录接口限流。

首次启动只创建新表，不自动迁移旧表或给历史会话分配用户。如果已有旧数据库，先备份，在部署新版、创建账号后执行以下 SQL 补充归属列，并明确选择历史数据的拥有者：

```sql
ALTER TABLE conversation_records
    ADD COLUMN IF NOT EXISTS user_id VARCHAR REFERENCES users(id);
CREATE INDEX IF NOT EXISTS ix_conversation_records_user_id
    ON conversation_records(user_id);
-- 将下面的用户名替换为实际创建的账号。
UPDATE conversation_records
SET user_id = (SELECT id FROM users WHERE username = 'bruce')
WHERE user_id IS NULL;
```

新库不需要上述 SQL。没有归属的历史会话不会通过业务 API 暴露给任意用户。
