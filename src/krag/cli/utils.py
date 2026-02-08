"""CLI utility functions."""

import typer


def exit_with_code(code: int) -> None:
    """Exit the application with the specified exit code.

    This function wraps typer.Exit() to avoid inline noqa suppressions
    for B904 (raise without from inside except).

    Args:
        code: Exit code (0 for success, non-zero for errors)
    """
    raise typer.Exit(code)
