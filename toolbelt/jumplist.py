"""The taskbar right-click menu (Windows calls it a "jump list"), like Playnite's: recently played games plus tasks.

Windows draws this menu itself; Toolbelt only hands it the entries. Each entry is a shortcut that starts
`pythonw.exe main.py --play <key>` (a game) or `--open <screen>` (a task), with the game's own icon when it has
an .ico (Windows accepts .ico/.exe/.dll as icon sources, not .jpg/.png). The list belongs to Toolbelt's taskbar
identity (brand.APP_ID), so it shows on the pinned button and on the running window alike.
All through plain ctypes COM, same trick as brand.start_menu_shortcut.
"""
import ctypes
import sys
from pathlib import Path

import brand
from brand import _GUID, _PROPERTYKEY, _PROPVARIANT, _method

CLSID_DESTINATION_LIST = "{77F10CF0-3DB5-4966-B520-B7C54FD35ED6}"
IID_DESTINATION_LIST = "{6332DEBF-87B5-4670-90C0-5E57B408A49E}"
CLSID_OBJECT_COLLECTION = "{2D3468C1-36A7-43B6-AC24-D3F02FD9607A}"
IID_OBJECT_COLLECTION = "{5632B1A4-E38A-400A-928A-D4CD63230295}"
IID_OBJECT_ARRAY = "{92CA9DCD-5622-4BBA-A805-5E9F541BD8C9}"
CLSID_SHELL_LINK = "{00021401-0000-0000-C000-000000000046}"
IID_SHELL_LINK = "{000214F9-0000-0000-C000-000000000046}"
IID_PROPERTY_STORE = "{886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99}"
PKEY_TITLE = ("{F29F85E0-4FF9-1068-AB91-08002B27B3D9}", 2)

ole32 = ctypes.windll.ole32


_start_apps = {}


def store_app_icon(name):
    r"""For games installed by the Xbox app / Store (C:\XboxGames, WindowsApps): nobody may read their .exe, not even
    Explorer (the shell gives a blank page icon too, tried 15 Oct). Their logo is a plain PNG in their package, named in
    its manifest: find the Start-menu app named like the game (Minecraft → "Minecraft Launcher"), read its package's
    logo and take the biggest clean version (unplated, 256 px). Returns that PNG's path, or ''."""
    import re
    import subprocess
    if not _start_apps:
        try:
            done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-StartApps | ForEach-Object { $_.Name + \"`t\" + $_.AppID }"],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, creationflags=0x08000000)
            for line in done.stdout.splitlines():
                if "\t" in line and "!" in line:
                    title, appid = line.split("\t", 1)
                    _start_apps[title.strip()] = appid.strip()
        except Exception:
            return ""
    words = [w for w in re.split(r"[^a-z0-9]+", str(name).lower()) if len(w) >= 3]
    appid = next((a for t, a in _start_apps.items() if words and all(w in t.lower() for w in words)), "")
    if not appid:
        return ""
    family, app = appid.split("!", 1)
    script = ("$p = Get-AppxPackage | Where-Object { $_.PackageFamilyName -eq '%s' } | Select-Object -First 1; if ($p) { "
              "[xml]$m = Get-Content -LiteralPath (Join-Path $p.InstallLocation 'AppxManifest.xml'); "
              "$a = $m.Package.Applications.Application | Where-Object { $_.Id -eq '%s' } | Select-Object -First 1; "
              "$v = $a.VisualElements; $logo = @($v.Square44x44Logo, $v.Square150x150Logo, $m.Package.Properties.Logo) | Where-Object { $_ } | Select-Object -First 1; "
              "$p.InstallLocation + \"`t\" + $logo }") % (family.replace("'", ""), app.replace("'", ""))
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=30, creationflags=0x08000000)
        location, logo = (done.stdout.strip().splitlines() or [""])[-1].split("\t", 1)
    except Exception:
        return ""
    base = Path(location) / logo
    candidates = list(base.parent.glob(base.stem + "*" + base.suffix))
    if not candidates:
        return ""

    def rank(p):                                              # unplated 256 px first, then any 256, then the biggest file
        n = p.name.lower()
        return ("contrast" not in n, "altform-unplated_targetsize-256" in n, "targetsize-256" in n, "scale-400" in n, p.stat().st_size)
    return str(max(candidates, key=rank))


def icon_file(path, name=""):
    """Windows menus only take .ico / .exe / .dll icons. A PNG or JPG game icon is turned into a small .ico in the cache."""
    from settings import DATA
    low = str(path or "").lower()
    if name and ("\\xboxgames\\" in low or "\\windowsapps\\" in low):
        logo = store_app_icon(name)                            # the locked Xbox / Store folders: the package's own logo
        if logo:
            return icon_file(logo) or icon_file(path)
    path = Path(path) if path else None
    if not path or not path.exists():
        return ""
    if path.suffix.lower() == ".ico":
        return str(path)
    import hashlib
    from PIL import Image, ImageOps
    folder = DATA / "cache" / "icons"
    folder.mkdir(parents=True, exist_ok=True)
    try:
        stamp = "%s|%d" % (path, path.stat().st_mtime_ns)
        target = folder / (hashlib.sha1(stamp.encode("utf-8")).hexdigest()[:16] + ".ico")
        if not target.exists():
            if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
                # an .exe, .dll or .lnk: Explorer can't always read the icon itself when the menu shows (Minecraft's
                # .exe lives in the locked C:\XboxGames, CurseForge was added as a Start-menu .lnk; both showed
                # Toolbelt's T, 15 Oct), so Toolbelt takes the icon out once, the way Explorer shows it, and keeps it
                import base64
                import io
                import shellicon
                data = shellicon.icon(str(path), 256)
                if not data:
                    return str(path) if path.suffix.lower() in (".exe", ".dll") else ""
                with Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1]))) as img:
                    img = img.convert("RGBA")
                    img.save(target, "ICO", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= max(img.size)] or [(16, 16)])
                return str(target)
            with Image.open(path) as img:
                img = ImageOps.exif_transpose(img).convert("RGBA")
                side = max(img.size)
                img = ImageOps.pad(img, (side, side), color=(0, 0, 0, 0))
                img.thumbnail((256, 256))
                sizes = [s for s in (16, 24, 32, 48, 64, 128, 256) if s <= max(img.size)] or [16]
                img.save(target, "ICO", sizes=[(s, s) for s in sizes])
        return str(target)
    except Exception:
        return ""


def _create(clsid, iid):
    obj = ctypes.c_void_p()
    hr = ole32.CoCreateInstance(ctypes.byref(_GUID(clsid)), None, 1, ctypes.byref(_GUID(iid)), ctypes.byref(obj))
    return obj if hr == 0 and obj else None


def _link(python, script, args, title, icon):
    """One menu entry: a shell link with a title (what the menu shows) and an icon."""
    link = _create(CLSID_SHELL_LINK, IID_SHELL_LINK)
    if not link:
        return None
    _method(link, 20, ctypes.c_wchar_p)(link, str(python))                                   # SetPath
    _method(link, 11, ctypes.c_wchar_p)(link, '"%s" %s' % (script, args))                    # SetArguments
    _method(link, 9, ctypes.c_wchar_p)(link, str(Path(script).parent))                       # SetWorkingDirectory
    ico = icon_file(icon, title) or str(brand.icon_path("cartridge"))
    _method(link, 17, ctypes.c_wchar_p, ctypes.c_int)(link, ico, 0)                          # SetIconLocation
    store = ctypes.c_void_p()
    _method(link, 0, ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(link, ctypes.byref(_GUID(IID_PROPERTY_STORE)), ctypes.byref(store))
    if store:
        key = _PROPERTYKEY(_GUID(PKEY_TITLE[0]), PKEY_TITLE[1])
        value = _PROPVARIANT(31, 0, 0, 0, title, None)                                        # VT_LPWSTR
        _method(store, 6, ctypes.POINTER(_PROPERTYKEY), ctypes.POINTER(_PROPVARIANT))(store, ctypes.byref(key), ctypes.byref(value))
        _method(store, 7)(store)                                                              # Commit
        _method(store, 2)(store)
    return link


def _collection(links):
    coll = _create(CLSID_OBJECT_COLLECTION, IID_OBJECT_COLLECTION)
    if not coll:
        return None
    for link in links:
        _method(coll, 5, ctypes.c_void_p)(coll, link)                                         # AddObject
    return coll


def update(games, python, script, tasks=None, app_id=brand.APP_ID, limit=10):
    """Rewrites Toolbelt's jump list: a "Recently played" group (newest first) and the tasks. Returns (ok, message)."""
    tasks = tasks if tasks is not None else [("Game library", "--open games", ""), ("Download a video", "--open video", ""),
                                             ("Cut out a picture", "--open bg", ""), ("Calculator (floating)", "--open calc-mini", "")]
    init = ole32.CoInitializeEx(None, 2)
    created = []
    try:
        dest = _create(CLSID_DESTINATION_LIST, IID_DESTINATION_LIST)
        if not dest:
            return False, "Windows wouldn't make a jump list."
        created.append(dest)
        _method(dest, 3, ctypes.c_wchar_p)(dest, app_id)                                      # SetAppID
        slots = ctypes.c_uint()
        removed = ctypes.c_void_p()
        hr = _method(dest, 4, ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))(
            dest, ctypes.byref(slots), ctypes.byref(_GUID(IID_OBJECT_ARRAY)), ctypes.byref(removed))      # BeginList
        if hr != 0:
            return False, "Windows refused the jump list (%d)." % hr
        if removed:
            created.append(removed)
        game_links = []
        for g in games[:limit]:
            link = _link(python, script, "--play " + g["key"], g["name"], g.get("icon", ""))
            if link:
                game_links.append(link)
        created += game_links
        if game_links:
            coll = _collection(game_links)
            created.append(coll)
            hr = _method(dest, 5, ctypes.c_wchar_p, ctypes.c_void_p)(dest, "Recently played", coll)      # AppendCategory
            if hr != 0:
                _method(dest, 11)(dest)                                                               # AbortList
                return False, "Windows refused the games list (%d)." % hr
        task_links = [l for l in (_link(python, script, args, title, icon) for title, args, icon in tasks) if l]
        created += task_links
        if task_links:
            coll = _collection(task_links)
            created.append(coll)
            _method(dest, 7, ctypes.c_void_p)(dest, coll)                                             # AddUserTasks
        hr = _method(dest, 8)(dest)                                                                   # CommitList
        return (hr == 0), ("Jump list updated: %d games" % len(game_links) if hr == 0 else "Saving the jump list failed (%d)." % hr)
    finally:
        for obj in created:
            try:
                _method(obj, 2)(obj)
            except Exception:
                pass
        if init in (0, 1):
            ole32.CoUninitialize()


def clear(app_id=brand.APP_ID):
    init = ole32.CoInitializeEx(None, 2)
    try:
        dest = _create(CLSID_DESTINATION_LIST, IID_DESTINATION_LIST)
        if not dest:
            return False
        hr = _method(dest, 10, ctypes.c_wchar_p)(dest, app_id)                                        # DeleteList
        _method(dest, 2)(dest)
        return hr == 0
    finally:
        if init in (0, 1):
            ole32.CoUninitialize()


if __name__ == "__main__":
    import games as _games
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    print(update(_games.all_games(), pythonw if pythonw.exists() else sys.executable, (Path(__file__).resolve().parents[1] / "main.py")))
