"""Tulis template import ke folder templates/."""

from pathlib import Path

from cloudsim.io.template_builder import write_templates

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    for path in write_templates(ROOT / "templates"):
        print(path)


if __name__ == "__main__":
    main()
