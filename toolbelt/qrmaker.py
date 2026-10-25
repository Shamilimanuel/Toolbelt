"""QR codes (Handy tools, 15 Oct), made with segno (agreed 15 Oct): a link or text, Wi-Fi, or a contact card.
Everything happens on this PC; nothing is looked up online.
"""
import base64
import io

import segno
from segno import helpers

LEVELS = {"l": "L", "m": "M", "q": "Q", "h": "H"}         # how much of the code may be damaged and still read: 7, 15, 25, 30 %


def make(kind, values, level="m"):
    """A segno QR code from the page's form. kind: text (also links), wifi or contact."""
    v = values if isinstance(values, dict) else {}
    err = LEVELS.get(str(level).lower(), "M")
    if kind == "wifi":
        ssid = str(v.get("ssid") or "").strip()
        if not ssid:
            raise ValueError("Type the Wi-Fi name.")
        security = str(v.get("security") or "WPA")
        return segno.make(helpers.make_wifi_data(ssid=ssid, password=str(v.get("password") or "") or None,
                                                 security=None if security == "none" else security, hidden=bool(v.get("hidden"))), error=err, micro=False)
    if kind == "contact":
        name = str(v.get("name") or "").strip()
        if not name:
            raise ValueError("Type a name.")
        return segno.make(helpers.make_mecard_data(name=name, phone=str(v.get("phone") or "") or None, email=str(v.get("email") or "") or None,
                                                   url=str(v.get("url") or "") or None), error=err, micro=False)
    text = str(v.get("text") or "")
    if not text.strip():
        raise ValueError("Type a link or some text.")
    if len(text) > 2000:
        raise ValueError("That's too long for a QR code people can scan (2000 characters at most).")
    return segno.make(text, error=err, micro=False)


def render(qr, dark="#000000", light="#FFFFFF", scale=10, border=4):
    """(svg text, png bytes) of the code in his colours. light "" = see-through background."""
    svg = io.BytesIO()
    qr.save(svg, kind="svg", scale=scale, border=border, dark=dark, light=light or None, xmldecl=False, svgns=True)
    png = io.BytesIO()
    qr.save(png, kind="png", scale=scale, border=border, dark=dark, light=light or None)
    return svg.getvalue().decode("utf-8"), png.getvalue()


def preview(kind, values, level="m", dark="#000000", light="#FFFFFF"):
    qr = make(kind, values, level)
    svg, png = render(qr, dark, light, 8)
    return {"ok": True, "svg": "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii"),
            "version": qr.version, "modules": qr.symbol_size(scale=1, border=0)[0], "size": len(png)}


def contrast_ok(dark, light):
    """Phones read dark-on-light best; a code that's too pale or inverted often fails."""
    def lum(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
        return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    if not light:
        return True
    d, l = lum(dark), lum(light)
    return l > d and (l + .05) / (d + .05) >= 3
