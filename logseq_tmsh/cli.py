import typer

app = typer.Typer()


@app.callback(invoke_without_command=True)
def main() -> None:
    """LogSeq time-tracking CLI."""


@app.command()
def today() -> None:
    typer.echo("ok")
