import typer

app = typer.Typer()


def main() -> None:
    """LogSeq time-tracking CLI."""
    pass


@app.command(name="today")
def today_cmd() -> None:
    """Show today's time entries."""
    typer.echo("ok")


app.callback(invoke_without_command=True)(main)
