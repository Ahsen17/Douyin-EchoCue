import contextlib
import os
import sys
from pathlib import Path

from litestar import Litestar

from aigc.base import Config
from aigc.base.config.constants import APP_NAME
from aigc.server import ApplicationCore


def create_app() -> Litestar:
    return Litestar.from_config(ApplicationCore())


def setup_environments() -> None:
    config = Config.get().app

    os.environ.setdefault("LITESTAR_APP", config.app_loc)
    os.environ.setdefault("LITESTAR_APP_NAME", APP_NAME)
    os.environ.setdefault("LITESTAR_HOST", config.host)
    os.environ.setdefault("LITESTAR_PORT", str(config.port))

    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    os.environ.setdefault("PYTHONUTF8", "1")
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(Exception):
                reconfigure(encoding="utf-8", errors="backslashreplace")


def entrypoint() -> None:
    """Application Entrypoint.

    This function sets up the environment and runs the Litestar CLI.
    If there's an error loading the required libraries, it will exit with a status code of 1.

    Returns:
        NoReturn: This function does not return as it either runs the CLI or exits the program.

    Raises:
        SystemExit: If there's an error loading required libraries.
    """

    current_path = Path(__file__).parent.parent.resolve()
    sys.path.append(str(current_path))

    setup_environments()

    try:
        from litestar.cli.main import litestar_group  # noqa: PLC0415

        sys.exit(litestar_group())
    except ImportError as exc:
        print(  # noqa: T201
            "Could not load required libraries. ",
            "Please check your installation and make sure you activated any necessary virtual environment",
        )
        print(exc)  # noqa: T201
        sys.exit(1)


if __name__ == "__main__":
    entrypoint()
