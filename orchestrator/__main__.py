from pathlib import Path

import click

from orchestrator.db import init_db


@click.group()
def cli():
    """Agentic Scaffold — orchestrate AI agents to build software."""
    pass


@cli.command()
@click.option("--spec", required=True, type=click.Path(exists=True), help="Path to master spec")
@click.option("--config", required=True, type=click.Path(exists=True), help="Path to config directory")
def run(spec, config):
    """Start a new scaffold run from a master spec."""
    from orchestrator.config import load_config
    cfg = load_config(config)
    conn = init_db(cfg.project.db_path)
    click.echo(f"Scaffold started. Spec: {spec}, DB: {cfg.project.db_path}")
    conn.close()


@cli.command()
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def resume(db):
    """Resume an interrupted scaffold run."""
    if not Path(db).exists():
        click.echo("No database found. Run 'scaffold run' first.")
        raise SystemExit(1)
    click.echo(f"Resuming from {db}")


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
    from orchestrator.db import get_connection
    conn = get_connection(db)
    if costs:
        rows = conn.execute("SELECT * FROM epic_costs").fetchall()
        for row in rows:
            click.echo(f"{row['epic_title']}: {row['total_tokens_in']+row['total_tokens_out']} tokens, {row['total_runs']} runs")
    if cycles:
        rows = conn.execute("SELECT * FROM cycle_hotspots").fetchall()
        for row in rows:
            click.echo(f"Task {row['task_id']}: {row['cycle_count']} cycles — {row['reasons']}")
    if agents:
        rows = conn.execute("SELECT * FROM agent_efficiency").fetchall()
        for row in rows:
            click.echo(f"{row['agent_role']} ({row['model']}): {row['success_rate_pct']:.0f}% success, {row['avg_ralph_iterations']:.1f} avg iterations")
    if not (costs or cycles or agents):
        total = conn.execute("SELECT COUNT(*) as cnt FROM tasks").fetchone()["cnt"]
        done = conn.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status='done'").fetchone()["cnt"]
        click.echo(f"Tasks: {done}/{total} done")
    conn.close()


@cli.command()
@click.option("--task", required=True, help="Task ID to inspect")
@click.option("--db", default="scaffold.db", help="Path to scaffold database")
def events(task, db):
    """Show event log for a specific task."""
    from orchestrator.db import get_connection
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
