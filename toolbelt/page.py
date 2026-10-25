"""The window's page as one piece of text: web\\index.html with the fonts, style.css and app.js put inside it.

pywebview starts a small web server for any page loaded from a file; handing it the page as text means no
server and no port (the Leyline way). The fonts go in as data too, so the app never contacts the internet.
Kept apart from main.py so the page test can build it without pywebview.
"""
import base64
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"

# family, weight (or range), file in web\fonts
FONTS = [
    ("Figtree", "400 800", "figtree.woff2"),
    ("Silkscreen", "400", "silkscreen-400.woff2"),
    ("Silkscreen", "700", "silkscreen-700.woff2"),
    ("JetBrains Mono", "500", "jetbrains-mono-500.woff2"),
]


def font_faces():
    rules = []
    for family, weight, name in FONTS:
        data = base64.b64encode((WEB / "fonts" / name).read_bytes()).decode("ascii")
        rules.append(f"@font-face {{ font-family: '{family}'; font-weight: {weight}; font-style: normal; font-display: block; "
                     f"src: url(data:font/woff2;base64,{data}) format('woff2'); }}")
    return "\n".join(rules)


def build_page(name="index.html", script="app.js"):
    html = (WEB / name).read_text(encoding="utf-8")
    css = font_faces() + "\n" + (WEB / "style.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="style.css">', "<style>\n" + css + "\n</style>")
    scripts = ""
    if script in ("app.js", "calcpop.js"):                      # the maths engine and the calculator device, before the page's own script
        for shared in ("calc.js", "mathedit.js", "device.js"):
            scripts += "<script>\n" + (WEB / shared).read_text(encoding="utf-8") + "\n</script>\n"
    scripts += "<script>\n" + (WEB / script).read_text(encoding="utf-8") + "\n</script>"
    html = html.replace('<script src="%s"></script>' % script, scripts)
    return html


def build_popup():
    """The tray pop-up (games), same fonts and looks."""
    return build_page("popup.html", "popup.js")


def build_calcpop():
    """The floating mini calculator."""
    return build_page("calcpop.html", "calcpop.js")


def build_guard():
    """App guard's warning (18 Oct), a small window above the clock like the tray pop-up."""
    return build_page("guard.html", "guard.js")
