"""Generate a multi-resolution Windows ICO from the project's supplied PNG."""

from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QImageReader, QPainter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "quietreader" / "assets" / "quietreader.png"
DESTINATION = ROOT / "src" / "quietreader" / "assets" / "quietreader.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def png_bytes(image: QImage) -> bytes:
    encoded = QByteArray()
    buffer = QBuffer(encoded)
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG"):
        raise RuntimeError("Could not encode an ICO image.")
    buffer.close()
    return bytes(encoded)


def make_icon_image(source: QImage, size: int) -> QImage:
    canvas = QImage(size, size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    limit = max(1, round(size * 0.92))
    scaled = source.scaled(
        limit,
        limit,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    painter = QPainter(canvas)
    painter.drawImage((size - scaled.width()) // 2, (size - scaled.height()) // 2, scaled)
    painter.end()
    return canvas


def main() -> None:
    source = QImageReader(str(SOURCE)).read()
    if source.isNull():
        raise SystemExit(f"Could not read the PNG icon: {SOURCE}")

    images = [(size, png_bytes(make_icon_image(source, size))) for size in SIZES]
    offset = 6 + 16 * len(images)
    entries = []
    payload = bytearray()
    for size, data in images:
        dimension = 0 if size == 256 else size
        entries.append(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset))
        payload.extend(data)
        offset += len(data)

    DESTINATION.write_bytes(struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + payload)
    print(f"Generated {DESTINATION} ({len(images)} sizes)")


if __name__ == "__main__":
    main()
