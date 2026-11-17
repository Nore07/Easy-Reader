"""Copy installed dependency notices without guessing license texts."""
from importlib.metadata import distribution
from pathlib import Path
import shutil


def main():
    root = Path(__file__).resolve().parents[1]
    destination = root / "dist" / "QuietReader" / "third-party"
    destination.mkdir(parents=True, exist_ok=True)
    lines = ["# Installed dependency metadata", "", "See docs/third-party.md in the source repository for distribution notes.", ""]
    for name in ["PySide6_Essentials", "shiboken6", "charset-normalizer", "defusedxml"]:
        item = distribution(name)
        lines.extend([f"## {name} {item.version}", "", str(item.metadata.get("License-Expression") or item.metadata.get("License") or "See upstream license"), ""])
        for file in item.files or []:
            if "license" in str(file).lower() or "copying" in str(file).lower():
                source = item.locate_file(file)
                if source.is_file():
                    target = destination / name / source.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
    (destination / "DEPENDENCIES.md").write_text("\n".join(lines), encoding="utf-8")
    shutil.copyfile(root / "docs" / "third-party.md", destination / "distribution-notes.md")


if __name__ == "__main__":
    main()
