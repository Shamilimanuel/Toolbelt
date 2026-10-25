"""Videos and pictures shown inside Toolbelt (his asks, 15 Oct: see the video while cutting a GIF, watch videos in
Toolbelt, before / after of an upscale).

A local video can't be handed to the page as text (hundreds of MB), and Toolbelt has no web server or port (a project
rule). So WebView2 asks Toolbelt itself: the page plays https://media.toolbelt.example/<id>/<name>, a made-up address
that never leaves the window; WebView2's WebResourceRequested event hands each request to `_answer`, which reads the
asked-for bytes straight from the file (HTTP 206 pieces, so seeking works and nothing is loaded whole).
Only files he opened in Toolbelt get an id; any other address gets "not found".
(WebView2's own folder mapping, SetVirtualHostNameToFolderMapping, doesn't reach a page loaded as text: tried, 15 Oct.)
"""
import hashlib
import mimetypes
import os
import re
import threading
from pathlib import Path
from urllib.parse import quote

HOST = "media.toolbelt.example"
PREFIX = "https://%s/" % HOST
SMALL = 8 * 1024 * 1024                                         # a closed range up to this is answered from memory

_files = {}                                                     # id -> path
_installed = set()                                              # windows (id) whose WebView2 answers our address
_handlers = []                                                  # keep the .NET delegates alive
_lock = threading.Lock()
TYPES = {".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska",
         ".gif": "image/gif", ".webp": "image/webp", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".avif": "image/avif",
         ".bmp": "image/bmp", ".mp3": "audio/mpeg", ".m4a": "audio/mp4", ".wav": "audio/wav", ".opus": "audio/ogg", ".ogg": "audio/ogg", ".flac": "audio/flac"}


def url(window, path):
    """The address the page can play `path` from. Raises OSError if the file is gone or the window isn't ready."""
    path = Path(path)
    if not path.is_file():
        raise OSError("That file is gone.")
    _install(window)
    key = hashlib.sha1(str(path.resolve()).lower().encode("utf-8")).hexdigest()[:16]
    with _lock:
        _files[key] = str(path)
    return PREFIX + key + "/" + quote(path.name)


def path_of(address):
    m = re.match(r"^https://" + re.escape(HOST) + r"/([0-9a-f]{16})/", str(address))
    return _files.get(m.group(1)) if m else None


def parse_range(header, size):
    """'bytes=100-' → (100, size-1); 'bytes=0-99' → (0, 99); no or bad header → None."""
    m = re.match(r"^\s*bytes=(\d*)-(\d*)\s*$", header or "")
    if not m or (not m.group(1) and not m.group(2)):
        return None
    if not m.group(1):                                          # 'bytes=-500': the last 500 bytes
        n = int(m.group(2))
        return (max(0, size - n), size - 1)
    start = int(m.group(1))
    end = int(m.group(2)) if m.group(2) else size - 1
    if start >= size:
        return (size, size - 1)
    return (start, min(end, size - 1))


def _install(window):
    form = getattr(window, "native", None)
    if form is None:
        raise OSError("The window isn't ready yet.")
    if id(window) in _installed:
        return
    from System import Action
    problem = {"error": None}

    def work():
        try:
            from Microsoft.Web.WebView2.Core import CoreWebView2WebResourceContext
            core = form.browser.webview.CoreWebView2
            if core is None:
                raise OSError("WebView2 isn't ready yet")
            core.AddWebResourceRequestedFilter(PREFIX + "*", CoreWebView2WebResourceContext.All)
            handler = lambda sender, args: _answer(sender, args)      # noqa: E731
            core.WebResourceRequested += handler
            _handlers.append(handler)
        except Exception as error:                              # noqa: BLE001 (reported to the page)
            problem["error"] = error

    if form.InvokeRequired:
        form.Invoke(Action(work))
    else:
        work()
    if problem["error"] is not None:
        raise OSError("The player couldn't start: %s" % str(problem["error"])[:120])
    _installed.add(id(window))


def _answer(core, args):
    """One request from the page for our made-up address: answer it with bytes from the file (or 'not found')."""
    uri = str(args.Request.Uri)
    if not uri.startswith(PREFIX):
        return
    env = core.Environment
    path = path_of(uri)
    if not path or not os.path.isfile(path):
        args.Response = env.CreateWebResourceResponse(None, 404, "Not Found", "Access-Control-Allow-Origin: *")
        return
    from System import Array, Byte
    from System.IO import FileAccess, FileMode, FileShare, FileStream, MemoryStream
    size = os.path.getsize(path)
    kind = TYPES.get(Path(path).suffix.lower()) or mimetypes.guess_type(path)[0] or "application/octet-stream"
    headers = args.Request.Headers
    wanted = parse_range(headers.GetHeader("Range") if headers.Contains("Range") else "", size)
    base = "Content-Type: %s\r\nAccept-Ranges: bytes\r\nAccess-Control-Allow-Origin: *\r\nCache-Control: no-store" % kind
    if wanted is None:
        stream = FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete)
        args.Response = env.CreateWebResourceResponse(stream, 200, "OK", base + "\r\nContent-Length: %d" % size)
        return
    start, end = wanted
    if start > end:
        args.Response = env.CreateWebResourceResponse(None, 416, "Range Not Satisfiable", base + "\r\nContent-Range: bytes */%d" % size)
        return
    # One piece of at most 8 MB, from memory. WebView2 reads a handed-over file from its start whatever its position
    # (tried 15 Oct), so "from byte N on" is answered with the next piece; the video player simply asks for the next.
    end = min(end, start + SMALL - 1)
    length = end - start + 1
    with open(path, "rb") as fh:
        fh.seek(start)
        data = fh.read(length)
    stream = MemoryStream(Array[Byte](data))
    args.Response = env.CreateWebResourceResponse(stream, 206, "Partial Content",
                                                  base + "\r\nContent-Length: %d\r\nContent-Range: bytes %d-%d/%d" % (length, start, end, size))
