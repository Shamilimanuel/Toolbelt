r"""PC care > Drivers (step 9, part 2): every device's driver, read from Windows, plus where official updates come from.

Decided 13 Oct: driver updates only from Windows Update or the maker's own site, a restore point first, the BIOS is
link-only. So Toolbelt never downloads a driver itself. It shows:
- every device with its driver version, date and maker (Win32_PnPSignedDriver, ~2 s),
- warnings: a device with a problem (Device Manager's yellow "!"), a driver older than 3 years on real hardware,
  and a generic Microsoft driver where the maker has its own,
- the motherboard and BIOS, with links to that exact board's support page and the chip makers' driver pages,
- and, when he asks, what Windows Update itself offers for drivers (it asks Microsoft's servers, so only on a button).
"""
import json
import re
import subprocess
import urllib.parse
from datetime import datetime

NO_WINDOW = 0x08000000

# which kind each device class is shown under (Device Manager's own names, in plain words)
GROUPS = {"DISPLAY": "Graphics", "MONITOR": "Screens", "MEDIA": "Sound", "AUDIOENDPOINT": "Sound", "NET": "Network & Wi-Fi", "BLUETOOTH": "Bluetooth",
          "HDC": "Storage", "SCSIADAPTER": "Storage", "DISKDRIVE": "Storage", "SYSTEM": "Motherboard & chipset", "USB": "USB",
          "HIDCLASS": "Mouse, keyboard & controllers", "KEYBOARD": "Mouse, keyboard & controllers", "MOUSE": "Mouse, keyboard & controllers",
          "CAMERA": "Camera", "IMAGE": "Camera", "PRINTER": "Printers", "BIOMETRIC": "Other", "FIRMWARE": "Motherboard & chipset", "PROCESSOR": "Processor"}
ORDER = ["Graphics", "Sound", "Network & Wi-Fi", "Bluetooth", "Motherboard & chipset", "Processor", "Storage", "USB", "Mouse, keyboard & controllers", "Screens", "Camera", "Printers", "Other"]
# makers whose own driver page we can link (official sites only)
MAKERS = [
    (("advanced micro devices", "amd"), "AMD", "https://www.amd.com/en/support/download/drivers.html"),
    (("nvidia",), "NVIDIA", "https://www.nvidia.com/en-us/drivers/"),
    (("intel",), "Intel", "https://www.intel.com/content/www/us/en/support/detect.html"),
    (("realtek",), "Realtek", ""),                             # Realtek sends people to the board maker for onboard sound / network
    (("tp-link",), "TP-Link", "https://www.tp-link.com/support/download/"),
    (("logitech",), "Logitech", "https://support.logi.com/hc/en-us/articles/360025297893"),
    (("roccat", "turtle beach"), "ROCCAT / Turtle Beach", "https://support.turtlebeach.com/"),
    (("steelseries",), "SteelSeries", "https://steelseries.com/gg"),
    (("razer",), "Razer", "https://www.razer.com/synapse-3"),
    (("corsair",), "Corsair", "https://www.corsair.com/us/en/s/downloads"),
]
BOARD_PAGES = {"asus": "https://rog.asus.com/search/?keyword=%s", "asustek": "https://rog.asus.com/search/?keyword=%s",
               "micro-star": "https://www.msi.com/search/%s", "msi": "https://www.msi.com/search/%s",
               "gigabyte": "https://www.gigabyte.com/Search?kw=%s", "asrock": "https://www.asrock.com/support/index.asp?model=%s"}


def _ps(script, timeout=60):
    done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    return done.stdout.strip()


def _date(text):
    """WMI dates come as 20260817000000.******+*** or '08/17/2026 02:00:00'."""
    text = str(text or "")
    m = re.match(r"^(\d{4})(\d{2})(\d{2})", text)
    if m:
        return "%s-%s-%s" % m.groups()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if m:
        return "%s-%02d-%02d" % (m.group(3), int(m.group(1)), int(m.group(2)))
    return ""


def maker_of(provider, manufacturer=""):
    text = (str(provider) + " " + str(manufacturer)).lower()
    for words, name, url in MAKERS:
        if any(w in text for w in words):
            return name, url
    return "", ""


def board():
    """The motherboard and BIOS, with the board's own support page."""
    raw = _ps("$b = Get-CimInstance Win32_BaseBoard; $i = Get-CimInstance Win32_BIOS; [pscustomobject]@{Maker=$b.Manufacturer; Model=$b.Product; Bios=$i.SMBIOSBIOSVersion; "
              "BiosDate=$i.ReleaseDate.ToString('yyyy-MM-dd')} | ConvertTo-Json -Compress")
    try:
        data = json.loads(raw or "{}")
    except ValueError:
        data = {}
    maker, model = str(data.get("Maker") or ""), str(data.get("Model") or "")
    page = ""
    for key, pattern in BOARD_PAGES.items():
        if key in maker.lower():
            page = pattern % urllib.parse.quote(model)
            break
    nice = "ASUS" if "asus" in maker.lower() else maker.replace(" COMPUTER INC.", "").replace(" Co., Ltd.", "").strip()
    return {"maker": nice, "model": model, "bios": str(data.get("Bios") or ""), "biosDate": str(data.get("BiosDate") or ""), "page": page}


def drivers(now=None):
    """Every device with a driver, grouped, with warnings. Newest problems first inside each group."""
    now = now or datetime.now()
    raw = _ps("Get-CimInstance Win32_PnPSignedDriver | Where-Object { $_.DeviceName } | Select-Object DeviceName,DeviceClass,DriverVersion,DriverDate,"
              "DriverProviderName,Manufacturer,DeviceID,InfName,IsSigned | ConvertTo-Json -Compress", timeout=90)
    problems = _ps("Get-CimInstance Win32_PnPEntity | Where-Object { $_.ConfigManagerErrorCode -ne 0 } | Select-Object DeviceID,ConfigManagerErrorCode | ConvertTo-Json -Compress")
    try:
        items = json.loads(raw or "[]")
        items = items if isinstance(items, list) else [items]
    except ValueError:
        items = []
    try:
        bad = json.loads(problems or "[]")
        bad = {b["DeviceID"]: b["ConfigManagerErrorCode"] for b in (bad if isinstance(bad, list) else [bad]) if b}
    except (ValueError, TypeError, KeyError):
        bad = {}
    out, seen = [], set()
    for d in items:
        cls = str(d.get("DeviceClass") or "").upper()
        name = str(d.get("DeviceName") or "")
        group = GROUPS.get(cls)
        if not group:
            continue
        provider = str(d.get("DriverProviderName") or "")
        device_id = str(d.get("DeviceID") or "")
        hardware = not device_id.upper().startswith(("ROOT\\", "SWD\\", "ACPI_HAL", "UMB\\", "STORAGE\\VOLUME", "HTREE"))
        key = (name.lower(), str(d.get("DriverVersion")))
        if key in seen:
            continue
        seen.add(key)
        date = _date(d.get("DriverDate"))
        age = 0
        if date:
            try:
                age = (now - datetime.strptime(date, "%Y-%m-%d")).days
            except ValueError:
                age = 0
        maker, maker_page = maker_of(provider, d.get("Manufacturer"))
        state, why = "ok", ""
        if device_id in bad:
            state, why = "problem", "Device Manager shows a problem with this device (code %s)." % bad[device_id]
        elif provider.lower() == "microsoft" and hardware and maker and group in ("Graphics", "Sound", "Network & Wi-Fi", "Bluetooth"):
            state, why = "generic", "Uses Windows' basic driver; %s has its own, usually with more features." % maker
        elif provider.lower() == "microsoft" and hardware and group in ("Graphics",):
            state, why = "generic", "Uses Windows' basic display driver: install the graphics maker's driver."
        elif age > 3 * 365 and hardware and provider.lower() != "microsoft":
            state, why = "old", "This driver is %d years old. Check the maker's page for a newer one." % (age // 365)
        out.append({"name": name, "group": group, "version": str(d.get("DriverVersion") or ""), "date": date, "age": age, "provider": provider,
                    "maker": maker or provider, "page": maker_page, "state": state, "why": why, "signed": bool(d.get("IsSigned")), "hardware": hardware,
                    "inf": str(d.get("InfName") or "")})
    rank = {"problem": 0, "generic": 1, "old": 2, "ok": 3}
    out.sort(key=lambda x: (ORDER.index(x["group"]) if x["group"] in ORDER else 99, rank[x["state"]], not x["hardware"], x["name"].lower()))
    return out


def windows_update_drivers():
    """What Windows Update offers for drivers right now (asks Microsoft's servers: only when he presses the button)."""
    script = ("$s = New-Object -ComObject Microsoft.Update.Session; $q = $s.CreateUpdateSearcher(); $q.ServerSelection = 2; "
              "$r = $q.Search(\"IsInstalled=0 and Type='Driver'\"); @($r.Updates | ForEach-Object { [pscustomobject]@{Title=$_.Title; "
              "Model=$_.DriverModel; Maker=$_.DriverManufacturer; Class=$_.DriverClass; Date=$_.DriverVerDate.ToString('yyyy-MM-dd'); Size=$_.MaxDownloadSize} }) | ConvertTo-Json -Compress")
    try:
        raw = _ps(script, timeout=240)
        data = json.loads(raw or "[]")
        data = data if isinstance(data, list) else [data]
        return {"ok": True, "updates": [d for d in data if d], "message": ""}
    except subprocess.TimeoutExpired:
        return {"ok": False, "updates": [], "message": "Windows Update took longer than 4 minutes. Try again later, or open Windows Update."}
    except ValueError:
        return {"ok": False, "updates": [], "message": "Windows Update didn't answer. Is the internet on?"}
