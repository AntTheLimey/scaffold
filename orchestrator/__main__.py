import os
from pathlib import Path

import anthropic
import click
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from orchestrator.agent_loader import AgentLoader
from orchestrator.config import load_config
from orchestrator.db import get_connection, init_db
from orchestrator.dispatcher import run_task
from orchestrator.event_bus import init_event_bus
from orchestrator.graph import build_graph
from orchestrator.init import format_detection, run_init
from orchestrator.nodes.onboarding import detect_project
from orchestrator.preflight import run_preflight
from orchestrator.state import initial_state
from orchestrator.task_tree import TaskTree
from orchestrator.telegram import TelegramBot


def _checkpoint_path(db_path: str) -> str:
    if db_path == ":memory:":
        return ":memory:"
    p = Path(db_path)
    return str(p.parent / f"{p.stem}_checkpoints{p.suffix}")


def _build_scaffold(cfg, spec_path: str, checkpointer):
    client = anthropic.Anthropic()
    bot = TelegramBot(
        token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
    )
    agents_dir = Path(__file__).parent / "agents"
    agent_loader = AgentLoader(agents_dir)
    graph = build_graph(
        client=client,
        bot=bot,
        repo_path=cfg.project.repo_path,
        branch_prefix=cfg.project.branch_prefix,
        spec_path=spec_path,
        agent_loader=agent_loader,
        agents_config=cfg.agents,
        checkpointer=checkpointer,
    )
    return graph, bot


@click.group()
def cli():
    """Agentic Scaffold — orchestrate AI agents to build software."""
    pass


@cli.command()
@click.option("--spec", required=True, type=click.Path(exists=True), help="Path to master spec")
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
@click.option("--project", default=None, help="Project name (from config/projects/)")
def run(spec, config, project):
    """Start a new scaffold run from a master spec."""
    try:
        cfg = load_config(config, project=project)
    except FileNotFoundError as e:
        click.echo(str(e))
        raise SystemExit(1) from e
    preflight_result = run_preflight(cfg)
    if not preflight_result.ok:
        for check in preflight_result.checks:
            click.echo(f"  {check.name} {'.' * (30 - len(check.name))} {check.status}")
        click.echo("\nPreflight failed. Fix the issues above and try again.")
        raise SystemExit(1)
    conn = init_db(cfg.project.db_path)
    init_event_bus(conn)

    with SqliteSaver.from_conn_string(_checkpoint_path(cfg.project.db_path)) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            tree = TaskTree(conn)
            task_id = tree.create(title="Root", level="epic", spec_ref=spec)
            state = initial_state(task_id=task_id, level="epic")

            click.echo(f"Scaffold started. Task: {task_id}, DB: {cfg.project.db_path}")

            run_task(graph, tree, state, task_id)
            click.echo("Run complete.")
        finally:
            bot.close()
    conn.close()


@cli.command()
@click.option("--task", required=True, help="Task ID to resume")
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
@click.option("--spec", default="", help="Path to master spec (needed if re-entering planning)")
@click.option("--project", default=None, help="Project name (from config/projects/)")
def resume(task, db, config, spec, project):
    """Resume an interrupted scaffold run."""
    if not Path(db).exists():
        click.echo("No database found. Run 'scaffold run' first.")
        raise SystemExit(1)

    try:
        cfg = load_config(config, project=project)
    except FileNotFoundError as e:
        click.echo(str(e))
        raise SystemExit(1) from e

    conn = get_connection(db)
    init_event_bus(conn)
    with SqliteSaver.from_conn_string(_checkpoint_path(db)) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            thread_config: RunnableConfig = {"configurable": {"thread_id": task}}
            click.echo(f"Resuming task {task} from {db}")
            result = graph.invoke(None, config=thread_config)
            click.echo(f"Resume complete. Status: {result.get('status', 'unknown')}")
        finally:
            bot.close()
    conn.close()


@cli.command()
@click.option("--task", required=True, help="Task ID to respond to")
@click.option(
    "--choice", required=True, type=click.Choice(["Approve", "Revise", "Override", "Cancel"])
)
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
@click.option("--spec", default="", help="Path to master spec (needed if re-entering planning)")
@click.option("--project", default=None, help="Project name (from config/projects/)")
def decide(task, choice, db, config, spec, project):
    """Provide a human decision for a paused task."""
    if not Path(db).exists():
        click.echo("No database found.")
        raise SystemExit(1)

    try:
        cfg = load_config(config, project=project)
    except FileNotFoundError as e:
        click.echo(str(e))
        raise SystemExit(1) from e

    conn = get_connection(db)
    init_event_bus(conn)
    with SqliteSaver.from_conn_string(_checkpoint_path(db)) as checkpointer:
        graph, bot = _build_scaffold(cfg, spec, checkpointer)
        try:
            thread_config: RunnableConfig = {"configurable": {"thread_id": task}}
            result = graph.invoke(
                Command(resume={"choice": choice}),
                config=thread_config,
            )
            click.echo(f"Decision applied: {choice} for task {task}")
            click.echo(f"Status: {result.get('status', 'unknown')}")
        finally:
            bot.close()
    conn.close()


@cli.command()
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
def preflight(config):
    """Validate scaffold prerequisites."""
    cfg = load_config(config)
    result = run_preflight(cfg)
    click.echo("\nPreflight Check")
    for check in result.checks:
        padding = "." * (30 - len(check.name))
        click.echo(f"  {check.name} {padding} {check.status}")
    if result.ok:
        click.echo("\nReady to run.")
    else:
        click.echo("\nPreflight failed.")
        raise SystemExit(1)


@cli.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.option("--config", default="config/", type=click.Path(), help="Scaffold config directory")
def init(repo_path, config):
    """Initialize a target repo for scaffold."""
    repo = Path(repo_path).resolve()
    detection = detect_project(repo)
    click.echo(f"\n{format_detection(detection)}\n")
    result = run_init(str(repo), config, detection=detection)
    click.echo("\nCreated:")
    if result["claude_md_action"] != "skip":
        click.echo(f"  {result['claude_md_path']} ({result['claude_md_lines']} lines)")
    click.echo(f"  {result['project_yaml_path']}")
    if result.get("overrides_path"):
        click.echo(f"  {result['overrides_path']}")
    project = result["project_name"]
    click.echo(
        f"\nRun 'scaffold run --spec <spec> --config {config} --project {project}' to start."
    )


@cli.command()
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option("--costs", is_flag=True, help="Show cost breakdown by epic")
@click.option("--cycles", is_flag=True, help="Show cycle hotspots")
@click.option("--agents", is_flag=True, help="Show agent efficiency metrics")
def report(db, costs, cycles, agents):
    """Show scaffold metrics and status."""
    if not Path(db).exists():
        click.echo("No database found.")
        raise SystemExit(1)
    conn = get_connection(db)
    if costs:
        rows = conn.execute("SELECT * FROM epic_costs").fetchall()
        for row in rows:
            total_tokens = row["total_tokens_in"] + row["total_tokens_out"]
            click.echo(f"{row['epic_title']}: {total_tokens} tokens, {row['total_runs']} runs")
    if cycles:
        rows = conn.execute("SELECT * FROM cycle_hotspots").fetchall()
        for row in rows:
            click.echo(f"Task {row['task_id']}: {row['cycle_count']} cycles — {row['reasons']}")
    if agents:
        rows = conn.execute("SELECT * FROM agent_efficiency").fetchall()
        for row in rows:
            success_rate = row["success_rate_pct"]
            avg_iters = row["avg_ralph_iterations"]
            msg = (
                f"{row['agent_role']} ({row['model']}): {success_rate:.0f}% success, "
                f"{avg_iters:.1f} avg iterations"
            )
            click.echo(msg)
    if not (costs or cycles or agents):
        total = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
        done_query = "SELECT COUNT(*) as cnt FROM tasks WHERE status='done'"
        done = conn.execute(done_query).fetchone()["cnt"]
        click.echo(f"Tasks: {done}/{total} done")
    conn.close()


@cli.command()
@click.option("--task", required=True, help="Task ID to inspect")
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def events(task, db):
    """Show event log for a specific task."""
    conn = get_connection(db)
    rows = conn.execute(
        "SELECT timestamp, event_type, event_data FROM events WHERE task_id = ? ORDER BY timestamp",
        (task,),
    ).fetchall()
    for row in rows:
        click.echo(f"[{row['timestamp']}] {row['event_type']}: {row['event_data']}")
    conn.close()


@cli.command()
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def pause(db):
    """Pause all scaffold work."""
    click.echo("Scaffold paused. Run 'scaffold resume' to continue.")


def main():
    cli()


if __name__ == "__main__":
    main()
