"""Worker entry point and CLI."""

import structlog
import typer

from .config import get_settings

logger = structlog.get_logger()
app = typer.Typer(help="Zippy Logistics agent workers")

AGENTS = [
    "customer_service",
    "order_management",
    "transportation",
    "resource_management",
    "payment_settlement",
    "platform_administration",
    "communication",
]


@app.command()
def start() -> None:
    """Start the heartbeat kernel loop for all registered agents."""
    from .kernel import Kernel

    logger.info("zippy-workers starting", version="0.0.1")
    Kernel(AGENTS).start_forever()


@app.command()
def health() -> None:
    """Check worker health."""
    s = get_settings()
    typer.echo(f"OK cap={s.max_tool_calls_per_tick} agents={len(AGENTS)}")


def cli() -> None:
    app()


if __name__ == "__main__":
    cli()
