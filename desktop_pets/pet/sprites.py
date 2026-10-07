"""Qt-Teil der Sprites: Sheet zerlegen, umfärben, ganzzahlig skalieren, spiegeln, Masken."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QBitmap, QColor, QImage, QPainter, QPixmap, QRegion, QTransform

from .pack import PetPack
from .recolor import build_color_map


@dataclass
class Frame:
    right: QPixmap
    left: QPixmap
    mask_right: QRegion
    mask_left: QRegion

    def pixmap(self, facing: int) -> QPixmap:
        return self.right if facing >= 0 else self.left

    def mask(self, facing: int) -> QRegion:
        return self.mask_right if facing >= 0 else self.mask_left


def recolored(image: QImage, color_map: dict[int, int]) -> QImage:
    if not color_map:
        return image
    img = image.convertToFormat(QImage.Format_ARGB32)
    for y in range(img.height()):
        for x in range(img.width()):
            px = img.pixel(x, y)
            alpha = (px >> 24) & 0xFF
            if alpha == 0:
                continue
            new = color_map.get(px & 0xFFFFFF)
            if new is not None:
                img.setPixel(x, y, (alpha << 24) | new)
    return img


def scale_nearest(image: QImage, factor: int) -> QImage:
    """Nur ganzzahlige Faktoren, Nearest-Neighbor – nichts verschwimmt."""
    factor = max(1, int(factor))
    return image.scaled(image.width() * factor, image.height() * factor,
                        Qt.IgnoreAspectRatio, Qt.FastTransformation)


def _mask(img: QImage) -> QRegion:
    return QRegion(QBitmap.fromImage(img.createAlphaMask()))


class SpriteSet:
    def __init__(self, pack: PetPack, factor: int, colors: dict[str, str] | None = None) -> None:
        self.pack = pack
        self.factor = max(1, int(factor))
        fw, fh = pack.sprite_size
        self.frame_w, self.frame_h = fw * self.factor, fh * self.factor
        sheet = QImage(str(pack.sprites_file)).convertToFormat(QImage.Format_ARGB32)
        sheet = recolored(sheet, build_color_map(pack.palette, colors))
        self.color_map = build_color_map(pack.palette, colors)
        self.frames: dict[str, list[Frame]] = {}
        mirror = QTransform().scale(-1, 1)
        for name, anim in pack.animations.items():
            frames = []
            for i in range(anim.frames):
                src = sheet.copy(QRect(i * fw, anim.row * fh, fw, fh))
                if src.isNull():
                    continue
                big = scale_nearest(src, self.factor)
                flipped = big.transformed(mirror, Qt.FastTransformation)
                frames.append(Frame(QPixmap.fromImage(big), QPixmap.fromImage(flipped), _mask(big), _mask(flipped)))
            if frames:
                self.frames[name] = frames
        if "idle" not in self.frames:
            raise ValueError(f"{pack.id}: keine idle-Frames im Sheet")

    def frame(self, name: str, index: int) -> Frame:
        frames = self.frames.get(name) or self.frames["idle"]
        return frames[index % len(frames)]

    # ---------- Zusatzgrafiken ----------
    def extra(self, filename: str, factor: int | None = None) -> QPixmap | None:
        """bed.png / bowl.png / food.png aus dem Paket (sonst Standardgrafik)."""
        from ..core import paths

        path = self.pack.optional_file(filename) or (paths.assets_dir() / filename)
        if not path.exists():
            return None
        img = QImage(str(path)).convertToFormat(QImage.Format_ARGB32)
        return QPixmap.fromImage(scale_nearest(img, factor or self.factor))


def pet_icon(pack: PetPack, size: int = 16, colors: dict[str, str] | None = None, zzz: bool = False) -> QPixmap:
    """16×16-Pixelkopf (Tray, Listen). Im Pause-Modus mit kleinem „Zzz“."""
    icon_file = pack.optional_file("icon.png")
    if icon_file is not None:
        img = QImage(str(icon_file)).convertToFormat(QImage.Format_ARGB32)
    else:
        fw, fh = pack.sprite_size
        img = QImage(str(pack.sprites_file)).copy(QRect(0, pack.animations["idle"].row * fh, fw, fh))
    img = recolored(img, build_color_map(pack.palette, colors))
    factor = max(1, size // max(1, img.width()))
    img = scale_nearest(img, factor)
    if zzz:
        # kleines „Z“ oben rechts (eigene Pixel, heller Grund für Lesbarkeit)
        painter = QPainter(img)
        f = max(1, factor)
        ox = img.width() - 5 * f
        painter.fillRect(QRect(ox, 0, 5 * f, 6 * f), QColor(255, 255, 225, 235))
        for r, row in enumerate(["KKK", "..K", ".K.", "K..", "KKK"]):
            for c, ch in enumerate(row):
                if ch == "K":
                    painter.fillRect(QRect(ox + (c + 1) * f, (r + 0) * f + f // 2, f, f), QColor("#0A246A"))
        painter.end()
    return QPixmap.fromImage(img)
