from __future__ import annotations

import math
import re
import importlib
import importlib.util
from collections import Counter
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET


class LocalKnowledgeService:
    """Small transparent TF-IDF retriever; replace this interface with SharePoint later."""

    def __init__(self, directory: str | Path = "knowledge_base"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def tokens(text):
        return re.findall(r"[a-z][a-z0-9-]{2,}", text.lower())

    def extract(self, path: Path) -> tuple[str, str]:
        suffix = path.suffix.lower()
        if suffix in {".txt", ".md"}:
            return path.read_text(encoding="utf-8", errors="ignore"), "indexed"
        if suffix == ".docx":
            try:
                with ZipFile(path) as archive:
                    root = ET.fromstring(archive.read("word/document.xml"))
                namespace = (
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                )
                return (
                    "\n".join(
                        node.text or ""
                        for node in root.findall(".//" + namespace + "t")
                    ),
                    "indexed",
                )
            except (BadZipFile, KeyError, ET.ParseError):
                return "", "invalid DOCX"
        if suffix == ".pdf":
            if importlib.util.find_spec("pypdf"):
                module = importlib.import_module("pypdf")
                reader = module.PdfReader(path)
                return (
                    "\n".join(page.extract_text() or "" for page in reader.pages),
                    "indexed",
                )
            return (
                "",
                "stored; PDF text extraction requires pypdf in the application environment",
            )
        return "", "unsupported"

    def documents(self):
        results = []
        for path in self.directory.glob("**/*"):
            if path.is_file() and path.suffix.lower() in {
                ".txt",
                ".md",
                ".docx",
                ".pdf",
            }:
                text, _ = self.extract(path)
                results.append((path, text))
        return results

    def sources(self):
        sources = []
        for path in sorted(self.directory.glob("**/*")):
            if path.is_file() and path.suffix.lower() in {
                ".txt",
                ".md",
                ".docx",
                ".pdf",
            }:
                text, status = self.extract(path)
                sources.append(
                    {
                        "path": path,
                        "name": path.name,
                        "type": path.suffix.lower(),
                        "size": path.stat().st_size,
                        "status": status,
                        "preview": text[:2000],
                    }
                )
        return sources

    def add(self, name: str, content: bytes) -> Path:
        safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", Path(name).name)
        if Path(safe).suffix.lower() not in {".txt", ".md", ".docx", ".pdf"}:
            raise ValueError(
                "Supported knowledge files are TXT, Markdown, DOCX, and PDF"
            )
        target = self.directory / "uploads" / safe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return target

    def delete(self, path: Path) -> None:
        resolved = path.resolve()
        if self.directory.resolve() not in resolved.parents:
            raise ValueError("Knowledge source is outside the configured directory")
        resolved.unlink(missing_ok=True)

    def retrieve(self, query: str, limit=3):
        docs = self.documents()
        q = Counter(self.tokens(query))
        results = []
        for path, text in docs:
            d = Counter(self.tokens(text))
            common = set(q) & set(d)
            score = sum((1 + math.log(q[t])) * (1 + math.log(d[t])) for t in common) / (
                math.sqrt(sum(v * v for v in q.values()) or 1)
                * math.sqrt(sum(v * v for v in d.values()) or 1)
            )
            if score:
                results.append(
                    {
                        "source": path.name,
                        "score": round(score, 3),
                        "excerpt": text[:500].strip(),
                    }
                )
        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]
