<div align="center">

# hoobnn-skills

Agent Skills for Claude Code and Codex, covering Git workflows, data science competitions and mathematical modeling.

[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[简体中文](README.md) · **English**

</div>

**hoobnn-skills** is a free, open-source (MIT) set of Agent Skills and a Claude Code plugin marketplace. It works with Claude Code, Codex, opencode, Grok Build and Antigravity CLI, and covers Git commit and worktree workflows, data science competition (Kaggle, Tianchi) workflows, math modeling contest (CUMCM, MCM / ICM) workflows and cross-agent delegation (agent-relay). The skills follow the [Agent Skills](https://agentskills.io) spec and install with `npx skills add`; Antigravity and Grok are also supported.

There are four groups:

- Git workflow: write Conventional Commits messages, manage git worktrees, roll back, clean up branches, and set up gitmoji + commitlint + husky in a project.
- Data science competitions (Kaggle, Tianchi, DataFountain and similar): repo setup at the start, experiment records, submission quota, retrospectives and defense prep, and coordinating several tasks at once.
- Math modeling contests (CUMCM, MCM / ICM): modeling, solving in code and writing the paper, with algorithm notes, LaTeX paper templates and Word paper formatting tools.
- Calling other agents: hand a task to, or get a second opinion from, another agent such as grok, agy, codex, opencode, pi, mcode (MiniMax Code), hermes, dsh (DeepSeek Harness) or claude over ACP.

Skill descriptions and prompts are written in Chinese.

## Install

### With npx skills

```bash
# Install every skill into Claude Code (global)
npx skills add hoobnn/hoobnn-skills --skill '*' -g -a claude-code -y

# Install a single skill into Codex
npx skills add hoobnn/hoobnn-skills --skill git-worktree -g -a codex -y
```

Start a new session afterwards. Describe what you want in plain words and the agent picks the matching skill, or call one directly with a slash command such as `/git-commit` or `/git-worktree add feature-ui`.

### From the plugin marketplace

Install through the plugin marketplace if you want skills to update with the plugin. Don't install the same agent both ways, or every skill shows up twice.

Claude Code (entry point becomes `/git-kit:git-commit`):

```text
/plugin marketplace add hoobnn/hoobnn-skills
/plugin install git-kit@hoobnn-skills
```

Codex:

```bash
codex plugin marketplace add hoobnn/hoobnn-skills
codex plugin add git-kit@hoobnn-skills
```

Grok:

```bash
grok plugin marketplace add hoobnn/hoobnn-skills
grok plugin install git-kit@hoobnn-skills
```

Available plugins: `git-kit`, `comp-kit`, `math-modeling`, `agent-relay`.

### Update

```bash
npx skills update -g -y
```

Skills installed from the plugin marketplace update with the plugin.

## Skills

### Git workflow (git-kit)

| Skill | What it does | Example |
|---|---|---|
| `git-commit` | Reads the diff and writes a Conventional Commits message that follows the project's commitlint config (emoji by default when there is none); suggests splitting mixed changes | `/git-commit --all` |
| `git-worktree` | Creates, lists and removes worktrees under `<repo>.worktrees/` next to the repo, optionally carrying over uncommitted changes | `/git-worktree add feature-ui` |
| `git-rollback` | Rolls a branch back to an earlier version: checks for uncommitted changes, makes a backup branch, previews, then runs reset or revert (merge-safe) | `/git-rollback --branch dev` |
| `git-clean-branches` | Removes merged (including squash / rebase merged) or stale branches; skips worktree-checked-out branches and never deletes on `upstream` | `/git-clean-branches --dry-run` |
| `gitmoji-commitlint-setup` | Adds commitlint and a husky commit-msg hook to a project, gitmoji style or plain Conventional Commits | "set up gitmoji commit rules for this project" |

### Data science competitions (comp-kit)

These are distilled from two competitions: a time-series decision task, and a CV / speech event with seven tasks running in parallel.

| Skill | What it does |
|---|---|
| `comp-init` | Sets up a competition repo: layout, an AGENTS.md entry file, archived rules and materials, data audit, validation scheme, score bounds and the smallest difference one submission can resolve |
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
| `agent-relay` | Talks to grok, agy, codex, opencode, pi, mcode (MiniMax Code), hermes, dsh (DeepSeek Harness) or claude over ACP (following the v2 draft, with v1 fallback) from inside the current agent to delegate a task, get a second opinion or compare several agents in parallel. Handles version negotiation, permission replies, model and reasoning effort, attachments (files and images), questions the agent asks back, session resume and output parsing, and returns one JSON object (answer, session ID, cost, protocol version, files changed, commands run, raw log folder, plus the questions when the agent asks back). A run that goes silent for too long is treated as stuck and ended early. Permissions follow each agent's own local config; operations it asks about are approved by default, or can all be denied | "ask grok whether this code has race conditions" |

## Supported agents

| Agent | `-a` value | Manual call |
|---|---|---|
| Claude Code | `claude-code` | `/git-commit` |
| Codex | `codex` | `$git-commit` |
| opencode | `opencode` | `/git-commit` |
| Grok Build | `grok` | `/git-commit` |
| Antigravity CLI (agy) | `antigravity-cli` | `/git-commit` |

`-a '*'` installs into every agent `npx skills` supports. A global install keeps the files in `~/.agents/skills`; Claude Code and Grok read the same copy through symlinks. pi and MiniMax Code (mcode) scan `~/.agents/skills` directly and need no `-a` of their own.

agy doesn't read `~/.agents/skills` globally. Register it once in `~/.gemini/config/skills.json` (use an absolute path; `~` is not expanded):

```json
{ "entries": [ { "path": "/Users/<you>/.agents/skills" } ] }
```

## FAQ

**Which agents are supported?** Claude Code, Codex, opencode, Grok Build and Antigravity CLI (agy); pi and MiniMax Code scan `~/.agents/skills` directly. See Supported agents above.

**How do I install, update and uninstall?** Install with `npx skills add hoobnn/hoobnn-skills --skill '*' -g -a claude-code -y`, update with `npx skills update -g -y`, and uninstall with `npx skills remove -g` (or delete the skill's folder under `~/.agents/skills`). Don't install through both `npx skills` and the plugin marketplace for the same agent, or the skills show up twice.

**Can I install just one skill?** Yes, by name, such as `--skill git-worktree`. Through the plugin marketplace the unit is a plugin: `git-kit`, `comp-kit`, `math-modeling` or `agent-relay`.

**How do I use them once installed?** Start a new session and describe what you need; the agent picks the matching skill. You can also call one by hand: `/git-commit` in Claude Code, opencode, Grok and agy, `$git-commit` in Codex.

**Do they use the network or upload my code?** A skill is a set of instructions for the agent plus a few helper scripts; none of it collects or uploads data. Only the parts that call outside services use the network: `math-modeling`'s paper search tool queries OpenAlex and AnySearch, and `agent-relay` starts the other agents you name on your machine, whose own network use follows their own configuration.

**A skill doesn't trigger or won't install?** Check that you started a new session after installing; that `name` in `SKILL.md` frontmatter matches the folder name, and is quoted if the value starts with `[` or `<` (otherwise `npx skills` skips it); and that you didn't install through both methods.

**How is this different from other skill collections?** It only holds the workflows the author uses repeatedly for Git, data science competitions, math modeling and cross-agent work, kept short. For broader general-purpose collections, look through the [Agent Skills](https://agentskills.io) ecosystem.

## Conventions for writing skills

- Skills live at `plugins/<plugin>/skills/<name>/SKILL.md`. The frontmatter `name` is lowercase with hyphens and matches the folder name; quote values that start with `[` or `<`, or `npx skills` skips the skill.
- Don't put a second `SKILL.md` inside a skill folder. Name sub-documents something else (e.g. `GUIDE.md`), or Codex and opencode register them as separate skills.
- Anything that needs a slash command is written as a skill, not under `commands/`.

## License

[MIT](LICENSE) © 2026 hoobnn. Free to use, modify and distribute, provided the copyright notice is kept. Exceptions:

- `plugins/math-modeling/skills/math-modeling/tools/docx`, `tools/pdf` and `tools/xlsx` contain code from Anthropic's official skills; see `LICENSE.txt` in each folder.
- math-modeling is adapted from [XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill) (MIT License).
