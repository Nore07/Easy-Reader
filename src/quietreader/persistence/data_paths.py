"""Application-relative data paths and migration from the previous location."""

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from quietreader.library.shelf import BOOKSHELF_DIR, SUPPORTED_SUFFIXES, UNCLASSIFIED, book_id_for_path


LEGACY_BOOKSHELF_DIR = "书架"
LEGACY_UNCLASSIFIED_DIR = "未分类"
STATE_FILES = ("state.json", "state.backup.json")


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def application_data_directory() -> Path:
    return application_root() / "data"


def legacy_migration_needed(legacy_directory: Path, destination: Path) -> bool:
    legacy = Path(legacy_directory)
    target = Path(destination)
    try:
        if legacy.resolve() == target.resolve() or target.is_symlink():
            return False
        if target.exists():
            if not target.is_dir():
                return False
            if any(entry.name != "quietreader.lock" for entry in target.iterdir()):
                return False
    except OSError:
        return False

    has_state = any((legacy / name).is_file() and not (legacy / name).is_symlink() for name in STATE_FILES)
    old_bookshelf = legacy / LEGACY_BOOKSHELF_DIR
    has_bookshelf = old_bookshelf.is_dir() and not old_bookshelf.is_symlink()
    return legacy.is_dir() and (has_state or has_bookshelf)


def _copy_bookshelf(source: Path, destination: Path) -> dict[str, str]:
    if source.is_symlink() or not source.is_dir():
        return {}

    categories = [entry for entry in source.iterdir() if entry.is_dir() and not entry.is_symlink()]
    categories.sort(key=lambda entry: (entry.name.casefold() != LEGACY_UNCLASSIFIED_DIR.casefold(), entry.name.casefold()))
    target_root = destination / BOOKSHELF_DIR
    category_names: dict[str, str] = {}
    used_names: set[str] = set()

    for category in categories:
        desired = UNCLASSIFIED if category.name.casefold() == LEGACY_UNCLASSIFIED_DIR.casefold() else category.name
        target_name = desired
        suffix = 2
        while target_name.casefold() in used_names:
            target_name = f"{desired} ({suffix})"
            suffix += 1
        used_names.add(target_name.casefold())
        category_names[category.name.casefold()] = target_name

        target_category = target_root / target_name
        target_category.mkdir(parents=True, exist_ok=True)
        for book in category.iterdir():
            if book.is_symlink() or not book.is_file() or book.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            shutil.copy2(book, target_category / book.name)

    return category_names


def _rewrite_state_paths(
    path: Path,
    old_bookshelf: Path,
    staged_bookshelf: Path,
    final_bookshelf: Path,
    category_names: dict[str, str],
) -> None:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, RecursionError):
        return
    if not isinstance(state, dict):
        return

    try:
        old_root = old_bookshelf.resolve()
    except OSError:
        return

    id_map: dict[str, str] = {}
    books = state.get("books")
    if isinstance(books, list):
        for record in books:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                continue
            try:
                old_path = Path(record["path"]).resolve()
                relative = old_path.relative_to(old_root)
            except (OSError, ValueError, RuntimeError):
                continue
            if len(relative.parts) != 2:
                continue
            category = category_names.get(relative.parts[0].casefold())
            if category is None:
                continue
            staged_path = staged_bookshelf / category / relative.parts[1]
            if not staged_path.is_file():
                continue

            old_id = record.get("id")
            new_path = final_bookshelf / category / relative.parts[1]
            new_id = book_id_for_path(new_path)
            record["path"] = str(new_path.resolve())
            record["id"] = new_id
            if isinstance(old_id, str):
                id_map[old_id] = new_id

    for key in ("positions", "bookmarks"):
        records = state.get(key)
        if isinstance(records, dict):
            state[key] = {id_map.get(book_id, book_id): value for book_id, value in records.items()}
    if isinstance(state.get("last_book"), str):
        state["last_book"] = id_map.get(state["last_book"], state["last_book"])

    path.write_text(json.dumps(state, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def migrate_legacy_data(legacy_directory: Path, destination: Path) -> bool:
    """Copy legacy settings and books into an empty app-root data folder."""
    legacy = Path(legacy_directory)
    target = Path(destination)
    if not legacy_migration_needed(legacy, target):
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".quietreader-migration-", dir=target.parent) as temporary:
        staged = Path(temporary) / "data"
        staged.mkdir()

        for name in STATE_FILES:
            source = legacy / name
            if source.is_file() and not source.is_symlink():
                shutil.copy2(source, staged / name)

        old_bookshelf = legacy / LEGACY_BOOKSHELF_DIR
        category_names = _copy_bookshelf(old_bookshelf, staged)
        new_bookshelf = staged / BOOKSHELF_DIR
        if category_names:
            for name in STATE_FILES:
                state_file = staged / name
                if state_file.is_file():
                    _rewrite_state_paths(state_file, old_bookshelf, new_bookshelf, target / BOOKSHELF_DIR, category_names)

        if target.exists():
            if target.is_symlink() or not target.is_dir():
                return False
            existing = list(target.iterdir())
            if any(entry.name != "quietreader.lock" for entry in existing):
                return False
            if existing:
                moved: list[Path] = []
                try:
                    for entry in staged.iterdir():
                        destination_entry = target / entry.name
                        if destination_entry.exists():
                            raise FileExistsError(destination_entry)
                        os.replace(entry, destination_entry)
                        moved.append(destination_entry)
                except OSError:
                    for entry in reversed(moved):
                        try:
                            os.replace(entry, staged / entry.name)
                        except OSError:
                            pass
                    raise
            else:
                target.rmdir()
                os.replace(staged, target)
        else:
            os.replace(staged, target)
    return True
