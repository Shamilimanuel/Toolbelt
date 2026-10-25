r"""PC care > Ping & lag (step 9, part 2): pings a few places every second and tells where lag comes from.

It uses Windows' own ICMP call (IcmpSendEcho in iphlpapi.dll, like ping.exe), so no admin and nothing installed.
It only runs while the Ping & lag tab is open (start / stop), and keeps the last 2 minutes per target.
The verdict compares the targets: your router bad → your Wi-Fi / cable; router fine but the internet bad → your
internet provider; the internet fine but one game bad → that game's server.
"""
import ctypes
import socket
import struct
import subprocess
import threading
import time
from collections import deque
from ctypes import wintypes

NO_WINDOW = 0x08000000
iphlpapi = ctypes.windll.iphlpapi
iphlpapi.IcmpCreateFile.restype = wintypes.HANDLE
iphlpapi.IcmpSendEcho.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.WORD, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD]
iphlpapi.IcmpCloseHandle.argtypes = [wintypes.HANDLE]


class _ECHO_REPLY(ctypes.Structure):
    _fields_ = [("Address", wintypes.DWORD), ("Status", wintypes.ULONG), ("RoundTripTime", wintypes.ULONG), ("DataSize", wintypes.USHORT),
                ("Reserved", wintypes.USHORT), ("Data", ctypes.c_void_p), ("Ttl", ctypes.c_ubyte), ("Tos", ctypes.c_ubyte), ("Flags", ctypes.c_ubyte),
                ("OptionsSize", ctypes.c_ubyte), ("OptionsData", ctypes.c_void_p)]


def ping_once(ip, timeout_ms=1000):
    """Round trip in ms, or None when no answer came back."""
    handle = iphlpapi.IcmpCreateFile()
    if not handle or handle == wintypes.HANDLE(-1).value:
        return None
    try:
        addr = struct.unpack("<I", socket.inet_aton(ip))[0]
        data = ctypes.create_string_buffer(b"Toolbelt-ping", 13)
        size = ctypes.sizeof(_ECHO_REPLY) + 13 + 8
        reply = ctypes.create_string_buffer(size)
        n = iphlpapi.IcmpSendEcho(handle, addr, data, 13, None, reply, size, timeout_ms)
        if n == 0:
            return None
        echo = _ECHO_REPLY.from_buffer_copy(reply)
        return int(echo.RoundTripTime) if echo.Status == 0 else None
    finally:
        iphlpapi.IcmpCloseHandle(handle)


def router():
    """The default gateway (his router), asked from Windows once."""
    try:
        done = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                               "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | Select-Object -First 1).NextHop"],
                              capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW)
        ip = done.stdout.strip().splitlines()[0] if done.stdout.strip() else ""
        socket.inet_aton(ip)
        return ip
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return ""


# targets anyone can reach; games are added by host name (he can add his own)
DEFAULT_TARGETS = [("router", "Your router", ""), ("internet", "Internet (Cloudflare)", "1.1.1.1"), ("google", "Google", "8.8.8.8"),
                   ("discord", "Discord", "discord.com"), ("hypixel", "Hypixel", "mc.hypixel.net")]


def stats(samples):
    """ms now, average, jitter (how much it jumps), lost % over the samples (None = lost)."""
    got = [s for s in samples if s is not None]
    lost = 100.0 * (len(samples) - len(got)) / len(samples) if samples else 0.0
    if not got:
        return {"now": None, "avg": None, "jitter": None, "lost": round(lost, 1), "count": len(samples)}
    jitter = sum(abs(a - b) for a, b in zip(got, got[1:])) / (len(got) - 1) if len(got) > 1 else 0.0
    return {"now": samples[-1], "avg": round(sum(got) / len(got), 1), "jitter": round(jitter, 1), "lost": round(lost, 1), "count": len(samples)}


def verdict(by_key):
    """Where the lag comes from, from the stats per target (router, internet, games)."""
    r, net = by_key.get("router"), by_key.get("internet") or by_key.get("google")

    def bad(s, ms):
        return s and s["count"] >= 5 and ((s["lost"] or 0) >= 3 or (s["avg"] or 0) > ms or (s["jitter"] or 0) > ms / 3)

    if r and r["count"] >= 5 and (r["lost"] or 0) >= 100:
        return "bad", "Your router doesn't answer pings (some don't). Judging from the internet targets only."
    if bad(r, 20):
        return "bad", "The lag starts at home: your Wi-Fi or cable to the router is slow or drops packets. Try a cable, or move closer to the router."
    if bad(net, 80):
        return "warn", "Your home network is fine, but the line to the internet is slow or drops packets: that's your internet provider (or someone downloading)."
    games = [(k, s) for k, s in by_key.items() if k not in ("router", "internet", "google") and bad(s, 120)]
    if games:
        return "warn", "Your connection is fine; %s is slow or drops packets. That's that server, not you." % ", ".join(k for k, _ in games)
    if net and net["count"] >= 5:
        return "ok", "Your connection is fine."
    return "wait", "Measuring…"


class Monitor:
    """Pings every target once a second in its own thread while running."""

    def __init__(self):
        self.targets = []                      # [{key, name, host, ip}]
        self.samples = {}                      # key -> deque of ms / None (last 120)
        self.times = deque(maxlen=120)
        self.events = deque(maxlen=30)         # spikes and losses worth telling
        self._stop = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    def set_targets(self, extra=()):
        targets = []
        for key, name, host in list(DEFAULT_TARGETS) + [("custom:" + h, h, h) for h in extra]:
            ip = router() if key == "router" else host
            if not ip:
                continue
            try:
                ip = socket.gethostbyname(ip)
            except OSError:
                ip = ""
            targets.append({"key": key, "name": name, "host": host or ip, "ip": ip})
        with self._lock:
            self.targets = targets
            for t in targets:
                self.samples.setdefault(t["key"], deque(maxlen=120))
        return targets

    def running(self):
        return bool(self._thread and self._thread.is_alive())

    def start(self, extra=()):
        if self.running():
            return
        self.set_targets(extra)
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="ping", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            started = time.time()
            results = {}
            threads = []
            for t in list(self.targets):
                def one(t=t):
                    results[t["key"]] = ping_once(t["ip"], 900) if t["ip"] else None
                th = threading.Thread(target=one, daemon=True)
                th.start()
                threads.append(th)
            for th in threads:
                th.join(1.2)
            with self._lock:
                self.times.append(time.strftime("%H:%M:%S"))
                for t in self.targets:
                    q = self.samples.setdefault(t["key"], deque(maxlen=120))
                    ms = results.get(t["key"])
                    prev = [s for s in list(q)[-10:] if s is not None]
                    q.append(ms)
                    base = sum(prev) / len(prev) if prev else None
                    if ms is None and prev:
                        self.events.appendleft({"at": time.strftime("%H:%M"), "target": t["name"], "what": "lost a packet"})
                    elif ms is not None and base and ms > max(3 * base, base + 60):
                        self.events.appendleft({"at": time.strftime("%H:%M"), "target": t["name"], "what": "spike to %d ms (usually %d)" % (ms, base)})
            self._stop.wait(max(0.0, 1.0 - (time.time() - started)))

    def snapshot(self):
        with self._lock:
            per = {}
            for t in self.targets:
                q = list(self.samples.get(t["key"], []))
                per[t["key"]] = dict(stats(q), name=t["name"], host=t["host"], ip=t["ip"], samples=q[-120:])
            level, text = verdict({k: v for k, v in per.items()})
            return {"running": self.running(), "targets": per, "order": [t["key"] for t in self.targets], "verdict": {"level": level, "text": text}, "events": list(self.events)}
