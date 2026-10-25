"""Used by the hidden self-test (main.py --selftest). A hidden window doesn't load media (Chromium pauses it), so this
checks the two halves separately in the real WebView2 inside Toolbelt:
- the private folder mapping (viewer.py) serves a real video file, in pieces (HTTP 206, what seeking needs), also for a
  name with spaces and "ü";
- which codecs this WebView2 decodes (H.264, HEVC, VP9, AV1; MP4, WebM, MKV), via canPlayType / mediaCapabilities.
What doesn't decode gets a playable copy (media.preview_copy)."""
import json
import subprocess
import tempfile
import time
from pathlib import Path

import media
import viewer

CODECS = {"h264": 'video/mp4; codecs="avc1.640028"', "hevc": 'video/mp4; codecs="hvc1.1.6.L120.90"', "vp9": 'video/webm; codecs="vp09.00.10.08"',
          "av1": 'video/mp4; codecs="av01.0.08M.08"', "mkv h264": 'video/x-matroska; codecs="avc1.640028"'}


def run(window):
    folder = Path(tempfile.mkdtemp(prefix="toolbelt play "))
    path = folder / "clip ü 1.mp4"
    subprocess.run([str(media.ffmpeg()), "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30", "-t", "2",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], capture_output=True, creationflags=0x08000000, timeout=120)
    url = viewer.url(window, path)
    size = path.stat().st_size
    window.evaluate_js("""(function(){ window.__pc = {codecs: {}};
        var U = %s;
        fetch(U, {headers: {Range: 'bytes=0-99'}}).then(function (r) { return r.arrayBuffer().then(function (b) { window.__pc.fetch = r.status + ' ' + b.byteLength; }); })
          .catch(function (e) { window.__pc.fetch = 'error ' + e; });
        fetch(U, {headers: {Range: 'bytes=100-'}}).then(function (r) { return r.arrayBuffer().then(function (b) { window.__pc.tail = r.status + ' ' + b.byteLength; }); })
          .catch(function (e) { window.__pc.tail = 'error ' + e; });
        fetch(U.replace(/[0-9a-f]{16}/, '0000000000000000')).then(function (r) { window.__pc.unknown = r.status + ''; }).catch(function (e) { window.__pc.unknown = 'error ' + e; });
        var v = document.createElement('video'), C = %s;
        Object.keys(C).forEach(function (k) {
          var can = v.canPlayType(C[k]);
          window.__pc.codecs[k] = can || 'no';
          if (navigator.mediaCapabilities) navigator.mediaCapabilities.decodingInfo({type: 'file', video: {contentType: C[k], width: 1920, height: 1080, bitrate: 8000000, framerate: 60}})
            .then(function (i) { window.__pc.codecs[k] = (i.supported ? 'yes' : 'no') + (i.smooth ? ', smooth' : '') + (i.powerEfficient ? ', hardware' : ''); }).catch(function () {});
        });
      })()""" % (json.dumps(url), json.dumps(CODECS)))
    deadline = time.time() + 10
    state = {}
    while time.time() < deadline:
        state = json.loads(window.evaluate_js("JSON.stringify(window.__pc || {})") or "{}")
        if state.get("fetch") and state.get("tail") and state.get("unknown") and len(state.get("codecs", {})) == len(CODECS):
            time.sleep(0.5)
            state = json.loads(window.evaluate_js("JSON.stringify(window.__pc || {})") or "{}")
            break
        time.sleep(0.3)
    state["file size"] = size
    state["url"] = url.split("/")[2]
    return state
