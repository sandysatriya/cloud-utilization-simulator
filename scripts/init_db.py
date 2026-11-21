"""Inisialisasi database SQLite lokal (tanpa data)."""

import argparse
from pathlib import Path

from cloudsim.config import env_db_path
from cloudsim.db.migrate import migrate


def main() -> None:
    parser = argparse.ArgumentParser(description="Buat/migrasikan database aplikasi.")
    parser.add_argument("--db", type=Path, default=env_db_path())
    args = parser.parse_args()
    migrate(args.db)
    print(f"Database siap: {args.db}")


if __name__ == "__main__":
    main()
