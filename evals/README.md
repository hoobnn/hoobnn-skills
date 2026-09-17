# 触发评估（trigger evals）

给六个 skill 各配了 20 条查询（10 应触发 + 10 不应触发的近邻负例），用 `claude -p`
实测 description 的触发准确率。改过 description 或触发短语后，跑一遍再合入。

## 跑法

```bash
cd evals/runner
env -u CLAUDECODE python3 -m scripts.run_eval \
  --eval-set ../trigger/<skill>.json \
  --skill-path ../../plugins/<plugin>/skills/<skill> \
  --runs-per-query 3 --num-workers 4 --timeout 150 --verbose
```

判读：`Results: N/20 passed`；应触发用例 `triggers/runs ≥ 2/3` 才算命中。整轮约 60 次
`claude -p` 调用，注意账号用量限额——限额撞上后超时会全部静默判「未触发」，表现为
应触发用例整片 0/3，先跑一条手动 `claude -p` 确认 API 正常再下结论。

## 本目录的 runner 相对 skill-creator 原版修了三个 bug

原版 `run_eval.py`（skill-creator 插件 ea0a38e1d671）在当前模型下会把真触发判成未触发：

1. **thinking 块误判**：兜底分支收到第一个 `assistant` 事件就 `return triggered`，
   但带 thinking 的模型第一个 assistant 事件只含 thinking 块，真正的 `Skill` 调用
   在后面。改为只有出现 tool_use 才返回。
2. **并行 worker 共享命令目录**：临时命令都写在同一 `.claude/commands/`，6 路并行时
   `claude -p` 会调用到别的 worker 的同义命令，原 worker 判未触发。改为每个运行
   独占 `runs/<uuid>/` 项目目录，结束即删。
3. **先探查后触发被判死**：模型先 `ls` 仓库再调 skill 是正常行为，原版把「第一个
   工具不是 Skill」直接判失败。改为放宽到 4 轮内（`--max-turns 4`）调用即算触发。

另两条运行要求：评估目录必须**不含任何真实项目文件**（空目录即可，命令文件由脚本
创建），并用 `--settings '{"enabledPlugins":{"comp-kit@hoobnn-skills":false,"git-kit@hoobnn-skills":false}}'`
禁掉已安装的同名插件再测，否则测的是装好的版本而非工作区的 description。

## 2026-09-17 基线

装置修复后六个 skill 全部 20/20。评估发现并已修掉的两个真实缺口：

- gitmoji-commitlint-setup：排障类（「husky 装了钩子没生效」）与放置类（「monorepo
  里配置放哪」）触发偏弱，description 已补触发短语并复测 3/3。
- comp-submit：多赛题额度分配问题会误吸引单赛题的 comp-submit，description 已加
  「只管单赛题」边界，复测从 3/3 降到 1/3。

隔离评估的已知局限：一次只挂一个 skill，测不出多 skill 同时可见时的路由竞争；
跨 skill 边界（如 comp-submit vs comp-campaign）要靠 description 里的显式让渡，
并靠负例用例兜底。
