import typer

app = typer.Typer(help="Websearch CLI")


@app.callback()
def main():
    """Websearch CLI - Fetch URLs and search the web."""
    pass


@app.command()
def ping():
    """Check if the CLI is working."""
    typer.echo("pong")


if __name__ == "__main__":
    app()
