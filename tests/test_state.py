import json

from quietreader.domain.models import Settings, Position, restore_position
from quietreader.persistence.store import StateStore
from quietreader.desktop.geometry import visible_bounds


def test_settings_clamp_and_shortcut_validation():
    settings = Settings.from_dict({"font_size": 0, "opacity": 0.01, "line_height": 99, "theme": "bad", "hotkey": "PageDown"})
    assert settings.font_size == 14
    assert settings.opacity >= 0.55
    assert settings.line_height <= 2.5
    assert settings.theme == "system"
    assert settings.hotkey == "Ctrl+Alt+R"


def test_anchor_survives_layout_change():
    from quietreader.domain.models import Section
    sections = [Section("a", "一", "你好" * 100)]
    assert restore_position(sections, Position("a", 75)) == (0, 75)
    assert restore_position(sections, Position("missing", 999)) == (0, 200)


def test_atomic_state_and_backup_recovery(tmp_path):
    store = StateStore(tmp_path)
    store.state["books"] = [{"id": "a", "path": "book.txt", "title": "测试"}]
    store.save()
    store.state["settings"]["font_size"] = 25
    store.save()
    assert StateStore(tmp_path).state["settings"]["font_size"] == 25
    store.path.write_text("broken", encoding="utf-8")
    recovered = StateStore(tmp_path)
    assert recovered.state["books"][0]["id"] == "a"
    assert recovered.warning


def test_unknown_schema_is_preserved(tmp_path):
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": 999}), encoding="utf-8")
    store = StateStore(tmp_path)
    assert store.read_only
    store.save()
    assert json.loads(path.read_text())["version"] == 999


def test_removed_display_and_small_screen():
    assert visible_bounds([9000, 9000, 700, 800], [(0, 0, 1920, 1080)]) == (610, 140, 700, 800)
    x, y, w, h = visible_bounds([0, 0, 900, 900], [(0, 0, 600, 500)])
    assert 0 <= x and 0 <= y and x + w <= 600 and y + h <= 500
