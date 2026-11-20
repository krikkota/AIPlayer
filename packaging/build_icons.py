"""Generate desktop icons from the audio waveform shown in onboarding."""
from pathlib import Path
import struct

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer

ASSETS = Path(__file__).resolve().parents[1] / "player/assets"
MARK = ASSETS / "icons/audio-lines.svg"


def png(size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 1024, size / 1024)
    painter.setBrush(QColor("#202023"))
    painter.setPen(QPen(QColor("#38383c"), 8))
    painter.drawRoundedRect(QRectF(104, 104, 816, 816), 181, 181)
    QSvgRenderer(str(MARK)).render(painter, QRectF(238, 238, 548, 548))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"Could not encode icon at {size}px")
    return bytes(data)


def main():
    windows = (16, 24, 32, 48, 64, 128, 256)
    icons = {size: png(size) for size in {*windows, 512, 1024}}
    (ASSETS / "Player.png").write_bytes(icons[1024])
    header = bytearray(struct.pack("<HHH", 0, 1, len(windows)))
    offset = 6 + 16 * len(windows)
    for size in windows:
        data = icons[size]
        header.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    (ASSETS / "Player.ico").write_bytes(header + b"".join(icons[size] for size in windows))
    mac_types = {16: b"icp4", 32: b"icp5", 64: b"icp6", 128: b"ic07",
                 256: b"ic08", 512: b"ic09", 1024: b"ic10"}
    chunks = b"".join(struct.pack(">4sI", kind, len(icons[size]) + 8) + icons[size]
                      for size, kind in mac_types.items())
    (ASSETS / "Player.icns").write_bytes(struct.pack(">4sI", b"icns", len(chunks) + 8) + chunks)


if __name__ == "__main__":
    main()
