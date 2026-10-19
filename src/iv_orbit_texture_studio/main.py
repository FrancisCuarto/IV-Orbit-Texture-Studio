"""Punto de entrada de IV Orbit Texture Studio."""

from __future__ import annotations

import sys


def main() -> int:
    from iv_orbit_texture_studio.app.application import run

    return run()


if __name__ == "__main__":
    sys.exit(main())
