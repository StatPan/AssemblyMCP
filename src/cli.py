"""CLI tool for Assembly API testing."""

import json

import typer

from .utils.api_client import AssemblyAPIClient


def main(
    endpoint: str = typer.Argument(..., help="API endpoint (e.g., OPENSRVAPI)"),
    pindex: int = typer.Option(1, "--page", help="Page index"),
    psize: int = typer.Option(10, "--size", help="Page size"),
    params: str = typer.Option("{}", "--params", help="Additional params as JSON"),
    output: str = typer.Option(None, "--output", "-o", help="Save to file"),
):
    """Fetch data from Assembly API."""
    client = AssemblyAPIClient()

    extra_params = json.loads(params) if params != "{}" else {}
    extra_params.update({"pIndex": pindex, "pSize": psize})

    try:
        result = client.request(endpoint, params=extra_params)

        if output:
            with open(output, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            typer.echo(f"Saved to {output}")
        else:
            typer.echo(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from e


if __name__ == "__main__":
    typer.run(main)
