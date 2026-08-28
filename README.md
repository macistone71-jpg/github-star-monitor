# GitHub Star Monitor

这是 `macistone71-jpg` 的私有 Star 监控仓库。

## 监控方式

- 每 15 分钟检查一次该账号名下的全部公开仓库。
- 将当前 Stargazers 与上一次快照进行比较。
- 发现账号从名单中消失时，把取消记录追加到 `data/unstar-events.jsonl`。
- 新建的公开仓库会自动加入监控；本监控仓库自身会被排除。

每条取消记录包含：

```json
{
  "detected_at": "2026-08-28T10:00:00Z",
  "event": "unstar",
  "repository": "macistone71-jpg/example",
  "user_id": "123456",
  "user_login": "octocat"
}
```

`detected_at` 是监控发现变化的时间（UTC），并非 GitHub 提供的精确取消时间。

## 文件

- `data/stargazers.json`：最近一次有变化时保存的完整名单。
- `data/unstar-events.jsonl`：取消 Star 的追加日志；首次检测到取消后会出现记录。

## 手动运行

进入仓库的 **Actions → Monitor repository stars → Run workflow**。

## 限制

- 只能记录启用监控之后发生的变化，无法恢复过去的取消记录。
- 如果某人点 Star 后又在两次检查之间取消，轮询可能无法观察到这次短暂变化。
- 访问令牌保存在 GitHub Actions 加密 Secret `MONITOR_TOKEN` 中，不会写入仓库文件。
