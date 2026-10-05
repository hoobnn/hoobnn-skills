# hoobnn-skills: Agent Skills for Claude Code, Codex and opencode

[简体中文](README.md) · **English**

The Agent Skills I use day to day in Claude Code, Codex and opencode. They follow the [Agent Skills](https://agentskills.io) spec and install with `npx skills add`; Antigravity and Grok work too.

There are four groups:

- Git workflow: write Conventional Commits messages, manage git worktrees, roll back, clean up branches, and set up gitmoji + commitlint + husky in a project.
- Data science competitions (Kaggle, Tianchi, DataFountain and similar): repo setup at the start, experiment records, submission quota, retrospectives and defense prep, and coordinating several tasks at once.
- Math modeling contests (CUMCM, MCM / ICM): modeling, solving in code and writing the paper, with algorithm notes and Word / LaTeX paper templates.
- Calling other agents: hand a task to, or get a second opinion from, another CLI such as grok, agy, codex, opencode, pi, hermes or claude.

Skill descriptions and prompts are written in Chinese.

## Install

```bash
# Install every skill into Claude Code (global)
npx skills add hoobnn/hoobnn-skills --skill '*' -g -a claude-code -y

# Install a single skill into Codex
npx skills add hoobnn/hoobnn-skills --skill git-worktree -g -a codex -y

# Update installed skills
npx skills update -g -y
```

Start a new session afterwards. Describe what you want in plain words and the agent picks the matching skill, or call one directly with a slash command such as `/git-commit` or `/git-worktree add feature-ui`.

## Skills

### Git workflow (git-kit)

| Skill | What it does | Example |
|---|---|---|
| `git-commit` | Reads the diff and writes a Conventional Commits message that follows the project's commitlint config (emoji by default when there is none); suggests splitting mixed changes | `/git-commit --all` |
| `git-worktree` | Creates, lists and removes worktrees under `.worktree-<repo>/` next to the repo, optionally carrying over uncommitted changes | `/git-worktree add feature-ui` |
| `git-rollback` | Rolls a branch back to an earlier version interactively; dry-run by default, asks twice before running reset / revert | `/git-rollback --branch dev` |
| `git-clean-branches` | Removes merged or stale local / remote branches, with protected branches | `/git-clean-branches --dry-run` |
| `gitmoji-commitlint-setup` | Adds commitlint and a husky commit-msg hook to a project, gitmoji style or plain Conventional Commits | "set up gitmoji commit rules for this project" |

### Data science competitions (comp-kit)

These come out of two competitions I worked through: a time-series decision task, and a CV / speech event with seven tasks running in parallel.

| Skill | What it does |
|---|---|
| `comp-init` | Sets up a competition repo: layout, CLAUDE.md and AGENTS.md, archived rules and materials, data audit, validation scheme, score bounds and the smallest difference one submission can resolve |
| `comp-experiment` | Keeps experiments trustworthy: one variable at a time, folds grouped by data source, like-for-like baselines, graded evidence; also for judging whether an offline gain will show up on the leaderboard |
| `comp-submit` | Submission management: scripted checks before submitting, entry gates, evidence and receipts per submission, daily quota budget, probe submissions, B-leaderboard freeze |
| `comp-retrospective` | Retrospectives and defense prep: playbook, list of disproved ideas, offline vs. leaderboard calibration, slides and Q&A |
| `comp-campaign` | Running several tasks at once: dashboard, quota and who may submit, sharing machines, subagent rules, overnight watch and wake-ups |

### Math modeling (math-modeling)

| Skill | What it does |
|---|---|
| `math-modeling` | Three-role workflow for CUMCM / MCM (modeler, programmer, writer), with notes on 7 algorithm families, subagent review, and six helper tools: docx, latex, figure, xlsx, pdf and paper search |

### Calling other agents (agent-relay)

| Skill | What it does | Example |
|---|---|---|
| `agent-relay` | Runs grok, agy, codex, opencode, pi, hermes or claude from inside the current agent to delegate a task or get a second opinion. Handles each CLI's headless flags, read-only / write permissions, session resume and output parsing, and returns one JSON object (answer, session ID, usage, cost). Read-only by default; for agy and hermes read-only is only a prompt instruction | "ask grok whether this code has race conditions" |

### Volcengine Ark (ark-kit)

| Skill | What it does | Example |
|---|---|---|
| `seedream` | Generates and edits images with Seedream 5.0. lite handles image sets and web search; pro handles layer decomposition, interactive editing and transparent backgrounds. Incompatible options fail locally before any request, and images are saved straight to disk. Needs `ARK_API_KEY` | "split this poster into layers" |

## Supported agents

| Agent | `-a` value | Manual call |
|---|---|---|
| Claude Code | `claude-code` | `/git-commit` |
| Codex | `codex` | `$git-commit` |
| opencode | `opencode` | `/git-commit` |
| Grok Build | `grok` | `/git-commit` |
| Antigravity CLI (agy) | `antigravity-cli` | `/git-commit` |

`-a '*'` installs into every agent `npx skills` supports. A global install keeps the files in `~/.agents/skills`; Claude Code and Grok read the same copy through symlinks.

agy doesn't read `~/.agents/skills` globally. Register it once in `~/.gemini/config/skills.json` (use an absolute path; `~` is not expanded):

```json
{ "entries": [ { "path": "/Users/<you>/.agents/skills" } ] }
```

## Installing from the plugin marketplace

Use this if you want skills to update along with the plugin. Don't install the same agent both ways, or every skill shows up twice.

<details>
<summary>Commands for Claude Code / Codex / Grok</summary>

Claude Code (entry point becomes `/git-kit:git-commit`):

```
/plugin marketplace add hoobnn/hoobnn-skills
/plugin install git-kit@hoobnn-skills
```

Codex:

```
codex plugin marketplace add hoobnn/hoobnn-skills
codex plugin add git-kit@hoobnn-skills
```

Grok:

```
grok plugin marketplace add hoobnn/hoobnn-skills
grok plugin install git-kit@hoobnn-skills
```

Available plugins: `git-kit`, `comp-kit`, `math-modeling`, `agent-relay`, `ark-kit`.

</details>

## Notes for writing skills

- Skills live at `plugins/<plugin>/skills/<name>/SKILL.md`. The frontmatter `name` is lowercase with hyphens and matches the folder name; quote values that start with `[` or `<`, or `npx skills` skips the skill.
- Don't put a second `SKILL.md` inside a skill folder. Name sub-documents something else (e.g. `GUIDE.md`), or Codex and opencode register them as separate skills.
- Anything that needs a slash command is written as a skill, not under `commands/`.

## License

[MIT License](LICENSE), except:

- `plugins/math-modeling/skills/math-modeling/tools/docx`, `tools/pdf` and `tools/xlsx` contain code from Anthropic's official skills; see `LICENSE.txt` in each folder.
- math-modeling is adapted from [XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill) (MIT License).
