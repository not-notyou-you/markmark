"""Turn uploaded files into plain text the AI can read and the grader can inspect."""
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath

MAX_OUTPUT = 2000
TEXT_EXT = {".txt", ".md", ".py", ".r", ".sql", ".java", ".c", ".cpp", ".js", ".ts", ".html", ".csv", ".json"}
MAX_ZIP_DEPTH = 3
MAX_UNPACKED = 500 * 1024 * 1024
JUNK = ("__MACOSX", ".ipynb_checkpoints", "/.", ".DS_Store")


class Unreadable(ValueError):
    """The file was received but no text could be taken from it."""


def _join(value):
    return "".join(value) if isinstance(value, list) else (value or "")


def _clip(text):
    if len(text) <= MAX_OUTPUT:
        return text
    half = MAX_OUTPUT // 2
    return f"{text[:half]}\n...[{len(text) - MAX_OUTPUT} characters cut]...\n{text[-half:]}"


def _notebook(data):
    try:
        notebook = json.loads(data.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        raise Unreadable("broken notebook") from e
    parts = []
    for i, cell in enumerate(notebook.get("cells", []), 1):
        source = _join(cell.get("source"))
        if cell.get("cell_type") == "markdown":
            parts.append(f"### [Cell {i} - text]\n{source}")
        elif cell.get("cell_type") == "code":
            parts.append(f"### [Cell {i} - code]\n{source}")
            out = []
            for item in cell.get("outputs", []):
                kind = item.get("output_type")
                if kind == "stream":
                    out.append(_join(item.get("text")))
                elif kind in ("execute_result", "display_data"):
                    content = item.get("data", {})
                    if "text/plain" in content:
                        out.append(_join(content["text/plain"]))
                    if any(k.startswith("image/") for k in content):
                        out.append("[image output: not visible to the AI]")
                elif kind == "error":
                    out.append(f"ERROR {item.get('ename')}: {item.get('evalue')}")
            parts.append(f"[Output of cell {i}]\n" + (_clip("\n".join(out)) if out else "(none / not run)"))
    return "\n\n".join(parts)


def _pdf(data):
    from pypdf import PdfReader
    try:
        pages = [page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages]
    except Exception as e:
        raise Unreadable("broken PDF") from e
    text = "\n\n".join(p for p in pages if p.strip())
    if not text.strip():
        raise Unreadable("PDF has no text layer (scanned?)")
    return text


def _docx(data):
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            root = ET.fromstring(z.read("word/document.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        raise Unreadable("broken DOCX") from e
    return "\n".join("".join(t.text or "" for t in p.iter(f"{ns}t")) for p in root.iter(f"{ns}p")).strip()


def to_text(filename, data):
    ext = PurePosixPath(filename).suffix.lower()
    if ext == ".ipynb":
        text = _notebook(data)
    elif ext == ".pdf":
        text = _pdf(data)
    elif ext == ".docx":
        text = _docx(data)
    elif ext in TEXT_EXT:
        text = data.decode("utf-8", "replace")
    else:
        raise Unreadable(f"unsupported file type: {ext or filename}")
    if not text.strip():
        raise Unreadable("file is empty")
    return text.replace("\x00", "")


def unpack(filename, data, depth=0):
    """Yield (path, bytes), opening zips in memory. Archive paths are only labels, never written to disk."""
    if not filename.lower().endswith(".zip"):
        yield filename, data
        return
    if depth >= MAX_ZIP_DEPTH:
        return
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            infos = [i for i in z.infolist() if not i.is_dir()]
            if sum(i.file_size for i in infos) > MAX_UNPACKED:
                raise Unreadable("zip is too large when unpacked")
            prefix = re.sub(r"\.zip$", "", filename, flags=re.I)
            for info in infos:
                if any(j in "/" + info.filename for j in JUNK):
                    continue
                yield from unpack(f"{prefix}/{info.filename}", z.read(info), depth + 1)
    except zipfile.BadZipFile as e:
        raise Unreadable("broken zip") from e
