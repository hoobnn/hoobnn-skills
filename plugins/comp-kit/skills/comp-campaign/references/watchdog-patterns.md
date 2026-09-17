# 守夜与远程训练模式

## 1. 判活看产物，不看进程

```bash
# 错：进程存在 ≠ 任务在推进（KeepAlive 每 30 s 崩一次也「有 PID」）
launchctl list | grep <label>
# 对：产物计数随时间增长才是健康
ls <out>/pred | wc -l; find <out> -newermt '-10 minutes' | wc -l
```

启动即打印「预期产物数」，巡检比较增量；连续 N 轮无增量即报警。

## 2. 三态 ssh 检测

```sh
# 错：ssh 连接失败也返回非零，被判成「进程已消失」
until ! ssh HOST "pgrep -f PAT"; do sleep 60; done
# 对：远端输出可解析计数；连接失败时 $out 为空，与「计数为 0」区分得开
until out=$(ssh -o ConnectTimeout=8 HOST "pgrep -f '[p]attern' | wc -l" 2>/dev/null) \
      && [ -n "$out" ] && [ "$out" -eq 0 ]; do
  sleep 180
done
echo "确认：连接正常且进程已退出"
```

`pgrep -f` / `pkill -f` 的模式会匹配执行 shell 自身，用 `[p]attern` 字符类。
任何跨网络的条件检测，故障态与目标态不能共用同一个信号。

## 3. launchd / cron 的最小 PATH

launchd 给的 PATH 不含 `/opt/homebrew/bin`，交互式 shell 里 `which uv` 正常，人工复核看不出来。
修在 watcher 脚本而不是 plist（reload 也不丢）：

```bash
set -uo pipefail
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:$HOME/.local/bin:$PATH"
command -v uv >/dev/null || { echo "uv not found" >&2; exit 1; }   # 缺依赖一次性炸响
```

修复后 `launchctl kickstart -k gui/$(id -u)/<label>`。
下载解压类 watcher 用**内容指纹幂等**（同 SHA 不重解），加磁盘闸门（如剩余 < 20 G 停），
不要按时间戳命名解压目录（重试 482 次吃掉 105 G）。

## 4. 长训练可 resume

- `save-every ≤ 2` epoch，`last.pt` 含 optimizer / epoch / scaler；启动即把 PID、日志、断点路径写进 experiment-log。
- 虚拟机（WSL）会在宿主不重启时被干净关闭（systemd shutdown.target），不是 OOM；
  重启后先查异常进程（挖矿自启），再恢复训练，总控重新数并发。
- 崩溃或被内存守卫停掉的 run **不 resume**：删干净、日志改名 `.aborted.log`、从零重启，
  首轮指标与原运行逐位相同才算「重启干净」。例外：同一 run 自身的断点续训（代码未变）。
- 守望进程用带 `ServerAliveInterval` 的 ssh，rc=255 后重连；一次 255 不等于训练死亡，先看 `uptime`。
- 在 ssh 非交互会话里调宿主命令（powershell）需借活跃进程的 interop 句柄。

## 5. 后台训练的静默失败

- MPS + DataLoader `num_workers>0` 在 nohup 后台下静默退出（空日志、无产物、无报错）→ `--workers 0`。
- `cmd && nohup … &` 链启动前先确认 lint / 语法 RC=0，否则链在第一步就断。
- 训练在跑时不编辑其 import 的源文件。
- 「余量门控启动器」：连续 N 次采样显存 / 内存都高于安全阈值才启动，宁可等。

## 6. 内存守卫（阈值配执行路径）

```
available < 阈值 → 按预设顺序停臂（先停最年轻 / 最不重要的）→ TERM → 20 s → KILL
→ rm -rf 半截 run，日志改名 .aborted.log → 上报总控
```
