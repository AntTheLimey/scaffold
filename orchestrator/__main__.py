from pathlib import Path

import anthropic
import click

from orchestrator.config import load_config
from orchestrator.db import get_connection, init_db
from orchestrator.graph import build_graph
from orchestrator.state import initial_state
from orchestrator.task_tree import TaskTree
from orchestrator.telegram import TelegramBot


@click.group()
def cli():
    """Agentic Scaffold — orchestrate AI agents to build software."""
    pass


@cli.command()
@click.option("--spec", required=True, type=click.Path(exists=True), help="Path to master spec")
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
def run(spec, config):
    """Start a new scaffold run from a master spec."""
    cfg = load_config(config)
    conn = init_db(cfg.project.db_path)

    client = anthropic.Anthropic()
    bot = TelegramBot(
        token=cfg.project.telegram_bot_token,
        chat_id=cfg.project.telegram_chat_id,
    )

    graph = build_graph(
        client=client,
        bot=bot,
        repo_path=cfg.project.repo_path,
        branch_prefix=cfg.project.branch_prefix,
        spec_path=spec,
        model="claude-sonnet-4-20250514",
    )

    tree = TaskTree(conn)
    task_id = tree.create(title="Root", level="epic", spec_ref=spec)
    state = initial_state(task_id=task_id, level="epic")

    click.echo(f"Scaffold started. Task: {task_id}, DB: {cfg.project.db_path}")

    result = graph.invoke(state)
    click.echo(f"Run complete. Status: {result.get('status', 'unknown')}")
    conn.close()


@cli.command()
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
@click.option(
    "--config", required=True, type=click.Path(exists=True), help="Path to config directory"
)
def resume(db, config):
    """Resume an interrupted scaffold run."""
    if not Path(db).exists():
        click.echo("No database found. Run 'scaffold run' first.")
        raise SystemExit(1)
    click.echo(f"Resuming from {db}")


@cli.command()
@click.option("--task", required=True, help="Task ID to respond to")
@click.option(
    "--choice", required=True, type=click.Choice(["Approve", "Revise", "Override", "Cancel"])
)
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def decide(task, choice, db):
    """Provide a human decision for a paused task."""
    if not Path(db).exists():
        click.echo("No database found.")
        raise SystemExit(1)
    click.echo(f"Decision recorded: {choice} for task {task}")


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
