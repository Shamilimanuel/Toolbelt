"""Tests for drivers.py and ping.py on this PC: the real driver list and board, the warnings logic on made-up drivers,
a real ping to the router and the internet, a lost ping, the stats and the verdict rules. Windows Update is not asked
(that goes to Microsoft's servers and takes minutes)."""
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "toolbelt"))

import drivers                                                # noqa: E402
import ping                                                   # noqa: E402

failures = []
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def expect(label, condition):
    print(("ok    " if condition else "FAIL  ") + label)
    if not condition:
        failures.append(label)


# ---------- the real drivers ----------
t0 = time.time()
ds = drivers.drivers()
expect("drivers read from Windows (%d in %.1f s)" % (len(ds), time.time() - t0), len(ds) >= 20 and time.time() - t0 < 30)
expect("each has a group, a version and a state", all(d["group"] in drivers.ORDER and d["version"] and d["state"] in ("ok", "problem", "generic", "old") for d in ds))
expect("the graphics card is there", any(d["group"] == "Graphics" and d["hardware"] for d in ds))
expect("groups come in the planned order", [d["group"] for d in ds] == sorted([d["group"] for d in ds], key=drivers.ORDER.index))
b = drivers.board()
expect("the board is read with its own support page: %s %s" % (b["maker"], b["model"]), b["model"] and b["bios"] and (not b["maker"].startswith("ASUS") or b["page"].startswith("https://rog.asus.com/")))

# ---------- the warnings, on made-up drivers ----------
fake = ('[{"DeviceName":"Radeon","DeviceClass":"DISPLAY","DriverVersion":"1.0","DriverDate":"20260801000000.******+***","DriverProviderName":"Microsoft","Manufacturer":"Advanced Micro Devices, Inc.","DeviceID":"PCI\\\\VEN_1002"},'
        '{"DeviceName":"Old LAN","DeviceClass":"NET","DriverVersion":"2.0","DriverDate":"01/02/2019 00:00:00","DriverProviderName":"Realtek","Manufacturer":"Realtek","DeviceID":"PCI\\\\VEN_10EC"},'
        '{"DeviceName":"Broken BT","DeviceClass":"BLUETOOTH","DriverVersion":"3.0","DriverDate":"20260101","DriverProviderName":"TP-Link","Manufacturer":"TP-Link","DeviceID":"USB\\\\VID_1"},'
        '{"DeviceName":"Virtual thing","DeviceClass":"SYSTEM","DriverVersion":"4.0","DriverDate":"20100101","DriverProviderName":"Someone","Manufacturer":"Someone","DeviceID":"ROOT\\\\X"},'
        '{"DeviceName":"Printer queue","DeviceClass":"PRINTQUEUE","DriverVersion":"5.0","DriverDate":"20260101","DriverProviderName":"Microsoft","DeviceID":"SWD\\\\P"}]')
problems = '[{"DeviceID":"USB\\\\VID_1","ConfigManagerErrorCode":28}]'
with mock.patch.object(drivers, "_ps", side_effect=[fake, problems]):
    made = drivers.drivers(now=datetime(2026, 10, 15))
by = {d["name"]: d for d in made}
expect("a Microsoft driver on an AMD card is 'generic' with AMD's page", by["Radeon"]["state"] == "generic" and by["Radeon"]["page"].startswith("https://www.amd.com/"))
expect("a 7-year-old Realtek network driver is 'old'", by["Old LAN"]["state"] == "old" and "7 years" in by["Old LAN"]["why"])
expect("a device with error code 28 is a 'problem'", by["Broken BT"]["state"] == "problem" and "28" in by["Broken BT"]["why"])
expect("an old virtual device is not flagged; unknown classes are left out", by["Virtual thing"]["state"] == "ok" and not by["Virtual thing"]["hardware"] and "Printer queue" not in by)
expect("problems first inside a group order", made[0]["name"] == "Radeon")
expect("dates in both WMI styles", drivers._date("20260817000000.******+***") == "2026-08-17" and drivers._date("8/17/2026 02:00:00") == "2026-08-17" and drivers._date("") == "")
expect("only official maker pages", all(u.startswith("https://") for _w, _n, u in drivers.MAKERS if u))

# ---------- ping ----------
gw = ping.router()
expect("the router's address is known: %s" % gw, bool(gw))
ms = ping.ping_once("1.1.1.1")
expect("a real ping to 1.1.1.1 answers (%s ms)" % ms, ms is not None and ms < 1000)
expect("an address nobody has times out as lost", ping.ping_once("10.255.255.1", 400) is None)
s = ping.stats([10, 12, None, 14, 10])
expect("stats: average, jitter (the jumps 2, 2, 4 → 2.7), lost", s["avg"] == 11.5 and s["jitter"] == 2.7 and s["lost"] == 20.0 and s["now"] == 10)
good = {"count": 30, "lost": 0, "avg": 3, "jitter": 1}
net_ok = {"count": 30, "lost": 0, "avg": 12, "jitter": 2}
expect("verdict: all fine", ping.verdict({"router": good, "internet": net_ok})[0] == "ok")
expect("verdict: Wi-Fi", "home" in ping.verdict({"router": {"count": 30, "lost": 8, "avg": 40, "jitter": 30}, "internet": net_ok})[1])
expect("verdict: internet provider", "provider" in ping.verdict({"router": good, "internet": {"count": 30, "lost": 5, "avg": 150, "jitter": 40}})[1])
expect("verdict: a game's server", "hypixel" in ping.verdict({"router": good, "internet": net_ok, "hypixel": {"count": 30, "lost": 10, "avg": 300, "jitter": 90}})[1])
m = ping.Monitor()
m.start(["one.one.one.one"])
time.sleep(3.5)
snap = m.snapshot()
m.stop()
expect("the monitor pings every target each second (%d samples)" % snap["targets"]["internet"]["count"], snap["targets"]["internet"]["count"] >= 2 and "custom:one.one.one.one" in snap["order"])
time.sleep(1.5)
expect("and stops when told", not m.running())

print()
if failures:
    print("%d FAILED: %s" % (len(failures), ", ".join(failures)))
    sys.exit(1)
print("ALL PASSED (test_drivers_ping)")
