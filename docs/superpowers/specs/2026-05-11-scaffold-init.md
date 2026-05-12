# scaffold init

## Goal

Add a `scaffold init` CLI command that prepares a target repo for scaffold consumption: detect project context, interview the human, and generate CLAUDE.md + project config.

## Context

The scaffold's onboarding node detects languages, frameworks, and tooling at runtime, but has no way to gather human context (project description, conventions, off-limits areas). Without CLAUDE.md in the target repo, agents operate with minimal project understanding. This command fills that gap as a one-time setup step, run before `scaffold run`.

## Command Interface

```
scaffold init /path/to/target/repo [--config config/]
```

- `repo_path` is a required positional argument — the target repo to initialize.
- `--config` is the scaffold config directory (default: `config/`). This is where the project yaml gets written. If the directory or `projects/` subdirectory doesn't exist, init creates it.
- No API key required. No network calls. Pure detection + terminal interaction.
- Idempotent: running again on an initialized repo offers to overwrite, augment, or skip existing CLAUDE.md.

## Multi-Project Support

The scaffold config directory is restructured to support multiple projects:

```
config/
  agents.yaml          # shared workforce definition
  governance.yaml      # shared governance rules
  projects/
    webapp.yaml        # project-specific config
    api.yaml           # project-specific config
```

Each project yaml contains:

```yaml
repo_path: /absolute/path/to/repo
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold_{project_name}.db
```

`agents.yaml` and `governance.yaml` remain shared across all projects.

### CLI Changes for Multi-Project

`scaffold run` and other commands gain a `--project` flag:

```
scaffold run --spec spec.md --config config/ --project webapp
scaffold run --spec spec.md --config config/ --project api
```

The `--project` flag resolves to `config/projects/{name}.yaml`. If the project yaml does not exist, the command prints "Run `scaffold init /path/to/repo` first." and exits.

The old `project.yaml` at the config root is deprecated. If it exists and `--project` is not provided, it is used for backward compatibility. If `--project` is provided, the root `project.yaml` is ignored.

## Init Flow

### Step 1: Detect

Runs the existing `detect_project()` function from `orchestrator/nodes/onboarding.py` against the target repo. Displays a summary:

```
Detected:
  Languages ............. Python, TypeScript
  Frameworks ............ FastAPI, React
  Test framework ........ pytest
  Database .............. yes (psycopg in deps)
  Makefile .............. yes
  CLAUDE.md ............. missing
```

### Step 2: Interview

Three questions, asked interactively via `click.prompt()`:

1. **"What does this project do?"** — Required. No default. One sentence.
2. **"Any conventions not captured in existing docs? (press Enter to skip)"** — Optional. Default: empty.
3. **"Anything agents should avoid touching? (press Enter to skip)"** — Optional. Default: empty.

If CLAUDE.md already exists and is substantive (50+ lines as defined by `detect_project`), the interview is skipped and the user is asked: "CLAUDE.md already exists (N lines). Overwrite, augment, or skip?" via `click.Choice`.

- **Overwrite**: delete existing, regenerate from detection + interview.
- **Augment**: append detected sections that are missing from the existing file.
- **Skip**: leave CLAUDE.md unchanged.

If the choice is overwrite, the interview questions are asked. If augment, only question 1 is asked (for the project description header if missing).

### Step 3: Generate

Writes files to the target repo and the scaffold config directory.

#### CLAUDE.md

Generated in the target repo root. Template:

```markdown
# {answer to question 1}

## Architecture
{comma-separated: languages, frameworks detected}

## Development

### Key Commands
{Makefile targets if detected, formatted as code block}

### Testing
{test framework name, conventional test directory}

## Code Style
{detected linter/formatter config files and their key settings}

## Conventions
{answer to question 2}

## Off-Limits
{answer to question 3}
```

Rules:
- Sections with no content are omitted entirely. No empty headings.
- Makefile targets are extracted by parsing `Makefile` for lines matching `^target_name:`.
- Code style detection reads: `ruff.toml` / `pyproject.toml [tool.ruff]`, `.eslintrc*`, `biome.json`, `golangci-lint.yml`, `.prettierrc`. Reports the tool name and key settings (line length, indent style).
- Output should be 30-80 lines. Lean toward minimal — the human or AI can enrich later.

#### Project YAML

Written to `config/projects/{project_name}.yaml` where `project_name` is derived from the repo directory name (lowercased, hyphens for spaces).

```yaml
repo_path: /absolute/path/to/repo
branch_prefix: scaffold
max_concurrent_agents: 3
db_path: scaffold_{project_name}.db
```

#### .claude/agents/ overrides

Only generated if the human provided specific conventions or off-limits areas in the interview. In that case, a single `_project.md` file is written to `.claude/agents/_project.md` in the target repo containing the conventions and off-limits content, formatted for agent consumption. Individual specialist overrides are NOT generated by init — those are a manual customization.

### Step 4: Confirm

Print a summary of what was written:

```
Created:
  /path/to/repo/CLAUDE.md (47 lines)
  config/projects/myapp.yaml

Run 'scaffold run --spec <spec> --config config/ --project myapp' to start.
```

## Config Loading Changes

`load_config()` in `orchestrator/config.py` is updated:

- New function `load_project(config_dir: str, project_name: str) -> ProjectConfig` that reads from `config/projects/{project_name}.yaml`.
- The existing `load_config()` gains an optional `project` parameter. If provided, it loads the project config from the projects subdirectory. If not provided, it falls back to `config/project.yaml` at the root for backward compatibility.
- `ProjectConfig` is unchanged — same fields as today.

## CLI Changes

### New command: `scaffold init`

```python
@cli.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.option("--config", default="config/", type=click.Path(), help="Scaffold config directory")
def init(repo_path, config):
```

### Updated commands: run, resume, decide

All gain `--project` option:

```python
@click.option("--project", default=None, help="Project name (resolves to config/projects/{name}.yaml)")
```

When `--project` is provided, `load_config` uses `config/projects/{project}.yaml` for the project config. When not provided, falls back to `config/project.yaml`.

### Preflight integration

`scaffold run` already calls `run_preflight()`. The preflight check is updated to verify the project yaml exists when `--project` is provided.

## Onboarding Node

No functional changes. The onboarding node continues to run `detect_project()` and configure the specialist roster on every `scaffold run`. The `claude_md_quality` field remains informational. The onboarding node does NOT gate on CLAUDE.md presence — that's the init command's responsibility.

## What This Does NOT Do

- Call the Anthropic API or Claude CLI (no AI involved in init)
- Modify the scaffold's own agents or knowledge bases
- Install tools or change the target repo's dependencies
- Generate `.claude/settings.json` or hooks in the target repo
- Run on every `scaffold run` — it's a one-time command
