from dataclasses import asdict, dataclass, field
import math
import re
from quietreader.keys import binding_error, normalize_binding


@dataclass
class Section:
    id: str
    title: str
    text: str


@dataclass
class Book:
    id: str
    path: str
    title: str
    author: str = ""
    sections: list[Section] = field(default_factory=list)
    encoding: str = ""


@dataclass
class Position:
    section_id: str = ""
    offset: int = 0


def valid_hotkey(value: str) -> bool:
    from quietreader.keys import windows_hotkey
    return windows_hotkey(value) is not None


@dataclass
class Settings:
    font_size: int = 20
    font_family: str = "Microsoft YaHei"
    line_height: float = 1.8
    padding: int = 32
    letter_spacing: float = 0.5
    paragraph_spacing: int = 12
    opacity: float = 0.92
    background_color: str = ""
    text_color: str = ""
    language: str = "system"
    theme: str = "system"
    floating: bool = False
    always_on_top: bool = False
    close_to_tray: bool = True
    global_hotkey: bool = False
    hotkey: str = "Ctrl+Alt+R"
    next_key: str = "PgDown"
    previous_key: str = "PgUp"
    focus_key: str = "F10"

    @classmethod
    def from_dict(cls, raw):
        raw = raw if isinstance(raw, dict) else {}
        result = cls()
        for key, low, high, convert in [
            ("font_size", 14, 42, int), ("line_height", 1.2, 2.5, float),
            ("padding", 12, 72, int), ("letter_spacing", 0, 5, float),
            ("paragraph_spacing", 0, 40, int), ("opacity", 0, 1, float),
        ]:
            try:
                value = float(raw.get(key, getattr(result, key)))
                if math.isfinite(value):
                    setattr(result, key, convert(max(low, min(high, value))))
            except (ValueError, TypeError, OverflowError):
                pass
        for key in ["floating", "always_on_top", "close_to_tray", "global_hotkey"]:
            if type(raw.get(key)) is bool:
                setattr(result, key, raw[key])
        if raw.get("theme") in ("system", "light", "dark", "sepia"):
            result.theme = raw["theme"]
        color = raw.get("background_color")
        if isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            result.background_color = color.lower()
        color = raw.get("text_color")
        if isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            result.text_color = color.lower()
        if raw.get("language") in ("system", "zh_CN", "en"):
            result.language = raw["language"]
        if isinstance(raw.get("font_family"), str) and 0 < len(raw["font_family"]) <= 100:
            result.font_family = raw["font_family"]
        bindings = {key: normalize_binding(raw.get(key, getattr(result, key))) for key in ("next_key", "previous_key", "focus_key", "hotkey")}
        if not binding_error(bindings):
            for key, value in bindings.items():
                setattr(result, key, value)
        return result

    def to_dict(self):
        return asdict(self)


def restore_position(sections: list[Section], position: Position) -> tuple[int, int]:
    if not sections:
        return 0, 0
    index = next((i for i, section in enumerate(sections) if section.id == position.section_id), 0)
    try:
        offset = max(0, min(len(sections[index].text), int(position.offset)))
    except (TypeError, ValueError, OverflowError):
        offset = 0
    return index, offset
