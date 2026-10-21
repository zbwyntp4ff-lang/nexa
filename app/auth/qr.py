"""Local QR SVG so device login does not depend on a third-party image CDN."""
from __future__ import annotations

import io


def qr_svg(payload: str) -> str:
    """Return an SVG document for `payload`. Empty string if generation fails."""
    if not payload.strip():
        return ""
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except ImportError:
        return ""
    try:
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(image_factory=SvgPathImage)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode("utf-8")
    except (ValueError, OSError):
        return ""
