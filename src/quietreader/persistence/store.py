from copy import deepcopy
import json
import os
from pathlib import Path
import shutil

from quietreader.domain.models import Settings

VERSION = 1


def initial_state():
    return {"version": VERSION, "settings": Settings().to_dict(), "books": [], "positions": {}, "last_book": "", "window": [100, 100, 1000, 760]}


class StateStore:
    """Single GUI-thread writer; unknown future versions are never overwritten."""
    def __init__(self, directory: Path):
        self.path = Path(directory) / "state.json"
        self.backup = self.path.with_suffix(".backup.json")
        self.warning = ""
        self.read_only = False
        self.state = initial_state()
        self._load()

    def _load(self):
        for path in (self.path, self.backup):
            if not path.exists():
                continue
            try:
                if path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError("state too big")
                value = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("invalid schema")
                version = value.get("version", 0)
                if type(version) is not int or version not in (0, VERSION):
                    self.read_only = True
                    self.warning = "保存数据来自不支持的版本。已保护原文件，本次不会保存更改。"
                    return
                books, positions = value.get("books", []), value.get("positions", {})
                if not isinstance(books, list) or not isinstance(positions, dict):
                    raise ValueError("invalid records")
                clean = initial_state()
                clean["settings"] = Settings.from_dict(value.get("settings")).to_dict()
                clean["books"] = [b for b in books[:100] if isinstance(b, dict) and all(isinstance(b.get(k), str) for k in ("id", "path", "title"))]
                clean["positions"] = {k: p for k, p in positions.items() if isinstance(k, str) and isinstance(p, dict) and isinstance(p.get("section_id"), str) and type(p.get("offset")) is int}
                clean["last_book"] = value.get("last_book", "") if isinstance(value.get("last_book", ""), str) else ""
                bounds = value.get("window")
                if isinstance(bounds, list) and len(bounds) == 4 and all(type(v) is int and abs(v) < 100000 for v in bounds):
                    clean["window"] = bounds
                self.state = clean
                if path == self.backup:
                    self.warning = "上次保存数据损坏，已从备份恢复。"
                    # Keep damaged primary out of the backup rotation.
                    self.path.replace(self.path.with_suffix(".damaged.json")) if self.path.exists() else None
                return
            except (OSError, ValueError, TypeError, RecursionError):
                self.warning = "保存数据无法读取，已使用默认设置；原文件保留。"
        if self.path.exists():
            self.read_only = True

    def save(self):
        if self.read_only:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        data = deepcopy(self.state)
        data["version"] = VERSION
        with temp.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        if self.path.exists():
            backup_temp = self.backup.with_suffix(".tmp")
            shutil.copy2(self.path, backup_temp)
            os.replace(backup_temp, self.backup)
        os.replace(temp, self.path)
