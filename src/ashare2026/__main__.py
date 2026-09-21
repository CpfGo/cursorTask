from __future__ import annotations

import sys


def entry(argv: list[str] | None = None) -> int:
    full = list(sys.argv if argv is None else argv)
    rest = full[1:]
    frozen = bool(getattr(sys, "frozen", False))
    if frozen and not rest:
        from ashare2026.win_launcher import launch_console

        return launch_console()
    from ashare2026.cli import main

    return main(rest if argv is not None else None)


if __name__ == "__main__":
    raise SystemExit(entry())
