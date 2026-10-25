"""Reads the Playnite game library straight from its database files, read-only.

Playnite keeps its library in %APPDATA%\\Playnite\\library\\*.db. Those are LiteDB v4 files
(a small .NET document database). There is no Python package for them, so this module reads
the raw file format itself. Only the standard library is used.

How a LiteDB v4 file is laid out (all numbers are little-endian):

* The file is a row of 4096-byte pages. Every page starts with a 25-byte header:
      PageID u32 | PageType u8 | PrevPageID u32 | NextPageID u32 | ItemCount u16 | FreeBytes u16
      | TransactionID u16 | 6 reserved bytes
  PageType: 0 empty, 1 header, 2 collection, 3 index, 4 data, 5 extend.
  A "no page" link is 0xFFFFFFFF.
* A DATA page holds ItemCount blocks right after the header. Each block is
      Index u16 | ExtendPageID u32 | Size u16 | Size bytes of document
  A document that fits in a page sits inside its block (ExtendPageID = 0xFFFFFFFF). A big
  document has Size 0 and the whole document lives in EXTEND pages instead.
* An EXTEND page carries ItemCount bytes of document right after the header (at most 4071),
  and NextPageID points at the next piece. Follow the chain and glue the pieces together.
* A document is BSON (binary JSON): i32 total length, then (type byte, name, value) repeated,
  closed by a 0 byte. LiteDB stores .NET Guids as binary subtype 4 in .NET byte order,
  and dates as milliseconds since 1970 in UTC.

Nothing here ever opens a database for writing: the file is copied to a temp file first
(Playnite may be running) and the copy is read, then deleted.
"""
import os
import re
import shutil
import struct
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

PAGE_SIZE = 4096
HEADER_SIZE = 25
NO_PAGE = 0xFFFFFFFF
EMPTY_GUID = "00000000-0000-0000-0000-000000000000"
DATA_PAGE, EXTEND_PAGE = 4, 5
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# ---------- pages ----------

def _page_header(data, page_no):
    """The seven header fields of one page, or None when the page is not fully there."""
    start = page_no * PAGE_SIZE
    if start + HEADER_SIZE > len(data):
        return None
    page_id, page_type, prev_id, next_id, items, free, _tx = struct.unpack_from("<IBIIHHH", data, start)
    return {"id": page_id, "type": page_type, "prev": prev_id, "next": next_id, "items": items, "free": free}


def _extend_chain(data, page_no):
    """Glue the bytes of an extend page and everything chained after it. Stops on anything odd."""
    pieces, seen = [], set()
    while page_no != NO_PAGE and page_no not in seen:
        seen.add(page_no)  # a loop in a broken file must not hang us
        head = _page_header(data, page_no)
        if head is None or head["type"] != EXTEND_PAGE:
            break
        start = page_no * PAGE_SIZE + HEADER_SIZE
        pieces.append(data[start:start + min(head["items"], PAGE_SIZE - HEADER_SIZE)])
        page_no = head["next"]
    return b"".join(pieces)


def raw_documents(data):
    """Every stored document as raw BSON bytes, in file order. Walks all data pages."""
    docs = []
    for page_no in range(len(data) // PAGE_SIZE):
        head = _page_header(data, page_no)
        if head is None or head["type"] != DATA_PAGE:
            continue
        pos = page_no * PAGE_SIZE + HEADER_SIZE
        end = (page_no + 1) * PAGE_SIZE
        for _ in range(head["items"]):
            if pos + 8 > end:
                break
            _index, extend_id, size = struct.unpack_from("<HIH", data, pos)
            pos += 8
            if size:
                docs.append(data[pos:pos + size])
            elif extend_id != NO_PAGE:
                docs.append(_extend_chain(data, extend_id))
            pos += size
    return docs


# ---------- BSON ----------

def _bson_value(kind, data, pos):
    """One BSON value starting at pos. Returns (value, new position). Unknown types raise."""
    if kind == 0x01:
        return struct.unpack_from("<d", data, pos)[0], pos + 8
    if kind == 0x02:  # string: i32 length (includes the closing 0), utf-8 bytes, 0
        n = struct.unpack_from("<i", data, pos)[0]
        return data[pos + 4:pos + 4 + n - 1].decode("utf-8", "replace"), pos + 4 + n
    if kind in (0x03, 0x04):  # document / array (an array is a document with keys "0", "1", ...)
        doc, end = _bson_document(data, pos)
        return (list(doc.values()) if kind == 0x04 else doc), end
    if kind == 0x05:  # binary: i32 length, subtype, bytes. Subtype 4 is a Guid.
        n, subtype = struct.unpack_from("<iB", data, pos)
        raw = data[pos + 5:pos + 5 + n]
        if subtype == 4 and n == 16:
            return str(uuid.UUID(bytes_le=raw)), pos + 5 + n  # .NET byte order (verified against folder names)
        return raw.hex(), pos + 5 + n
    if kind == 0x07:
        return data[pos:pos + 12].hex(), pos + 12
    if kind == 0x08:
        return data[pos] != 0, pos + 1
    if kind == 0x09:  # milliseconds since 1970, UTC
        ms = struct.unpack_from("<q", data, pos)[0]
        try:
            return (EPOCH + timedelta(milliseconds=ms)).isoformat(timespec="seconds"), pos + 8
        except (OverflowError, ValueError):
            return "", pos + 8
    if kind == 0x0A:
        return None, pos
    if kind == 0x10:
        return struct.unpack_from("<i", data, pos)[0], pos + 4
    if kind == 0x12:
        return struct.unpack_from("<q", data, pos)[0], pos + 8
    if kind == 0x13:  # decimal (16 bytes): keep the raw bytes, Playnite doesn't use it
        return data[pos:pos + 16].hex(), pos + 16
    raise ValueError("unknown BSON type 0x%02x" % kind)


def _bson_document(data, pos):
    """Parse one document at pos. Returns (dict, position after it). Stops early but keeps what it got."""
    out = {}
    if pos + 4 > len(data):
        return out, len(data)
    end = pos + struct.unpack_from("<i", data, pos)[0]
    pos += 4
    try:
        while pos < end and pos < len(data):
            kind = data[pos]
            if kind == 0:
                break
            name_end = data.index(b"\0", pos + 1)
            name = data[pos + 1:name_end].decode("utf-8", "replace")
            out[name], pos = _bson_value(kind, data, name_end + 1)
    except (ValueError, struct.error, IndexError):
        pass  # a damaged field: return the fields read so far
    return out, end


def parse_document(raw):
    """Raw BSON bytes -> dict."""
    return _bson_document(raw, 0)[0]


# ---------- the public helpers ----------

def backup_bytes(name, library=None):
    """While Playnite runs it locks its database files. Playnite keeps zipped backups next to the library
    (Backup\\PlayniteBackup-<date>.zip, with library/games.db inside); the newest one is at most a day old."""
    import zipfile
    library = Path(library) if library else default_library_dir()
    folder = library.parent / "Backup"
    zips = sorted(folder.glob("PlayniteBackup-*.zip"), key=lambda p: p.stat().st_mtime) if folder.is_dir() else []
    for z in reversed(zips):
        try:
            with zipfile.ZipFile(z) as archive:
                return archive.read("library/" + name)
        except (OSError, KeyError, zipfile.BadZipFile):
            continue
    return b""


def load_bytes(path):
    """The bytes of a Playnite db file: a temp copy when possible, a plain read, else the newest backup. b'' if nothing works."""
    path = Path(path)
    if not path.is_file():
        return b""
    fd, copy = tempfile.mkstemp(suffix=".db", prefix="toolbelt_litedb_")
    os.close(fd)
    try:
        try:
            shutil.copy(path, copy)  # Playnite may have the real file open
            return Path(copy).read_bytes()
        except OSError:
            pass
        try:
            return path.read_bytes()  # a plain read-only open as a fallback
        except OSError:
            return backup_bytes(path.name, path.parent)
    finally:
        try:
            os.remove(copy)
        except OSError:
            pass


def read_collection(path):
    """All documents in a single-collection LiteDB v4 file, as dicts. Never raises; [] if unreadable."""
    path = Path(path)
    try:
        data = load_bytes(path)
        if len(data) < HEADER_SIZE + 27 or data[HEADER_SIZE:HEADER_SIZE + 27] != b"** This is a LiteDB file **":
            return []
        return [parse_document(raw) for raw in raw_documents(data) if raw]
    except Exception:
        return []


def default_library_dir():
    return Path(os.environ.get("APPDATA", "")) / "Playnite" / "library"


def games(library_dir=None):
    """Every Playnite game, newest played first. [] when Playnite isn't installed or the db is unreadable."""
    library = Path(library_dir) if library_dir else default_library_dir()
    try:
        if not (library / "games.db").is_file():
            return []
        sources = {s.get("_id"): s.get("Name", "") for s in read_collection(library / "sources.db")}
        exe = str(Path(os.environ.get("LOCALAPPDATA", "")) / "Playnite" / "Playnite.DesktopApp.exe")
        out = []
        for doc in read_collection(library / "games.db"):
            game_id = str(doc.get("_id") or "")
            if not game_id:
                continue
            def picture(field):
                """Icon, CoverImage and BackgroundImage are paths under library\\files (or absolute); '' when the file is gone."""
                rel = doc.get(field)
                if not isinstance(rel, str) or not rel:
                    return ""
                full = Path(rel) if Path(rel).is_absolute() else library / "files" / rel
                return str(full) if full.is_file() else ""

            icon = picture("Icon")
            text = doc.get("Description") if isinstance(doc.get("Description"), str) else ""
            text = re.sub(r"<[^>]+>", " ", text)                  # Playnite stores it as HTML
            text = re.sub(r"\s+", " ", text).strip()
            playtime = doc.get("Playtime") or 0
            source_id = doc.get("SourceId")
            out.append({
                "id": game_id,
                "name": doc.get("Name") or "",
                # an all-zero (or missing) SourceId = added by hand; Playnite shows those as "Playnite"
                "source": sources.get(source_id, "") if source_id and source_id != EMPTY_GUID else "Playnite",
                "installed": bool(doc.get("IsInstalled")),
                "hidden": bool(doc.get("Hidden")),
                "last_played": doc.get("LastActivity") or "",
                "playtime_seconds": int(playtime) if isinstance(playtime, (int, float)) else 0,
                "icon": icon,
                "cover": picture("CoverImage"),
                "background": picture("BackgroundImage"),
                "description": text[:1200],
                "install_dir": doc.get("InstallDirectory") or "",
                "play_command": [exe, "--start", game_id],
            })
        out.sort(key=lambda g: g["last_played"], reverse=True)  # "" (never played) sorts last
        return out
    except Exception:
        return []


if __name__ == "__main__":
    for g in games():
        print("%-28s %-10s %s" % (g["name"][:28], g["source"], g["last_played"]))
