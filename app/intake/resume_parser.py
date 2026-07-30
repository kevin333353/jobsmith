"""履歷檔案攝取：PDF / DOCX / 純文字 → 純文字。"""
from __future__ import annotations

import re
from io import BytesIO
from zipfile import BadZipFile, ZipFile

# 控制字元（含 NUL \x00）會殘留在 UTF-16 存的 .txt、或某些 PDF 的抽取結果裡。
# \x00 之後被當成 CLI 參數丟進 subprocess 會直接 ValueError("embedded null byte")，
# 其餘 C0/C1 控制字元也只是 LLM 雜訊。保留常見空白（\t \n \r），其餘一律移除。
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MAX_PDF_PAGES = 20
MAX_DOCX_ENTRIES = 500
MAX_DOCX_EXPANDED_BYTES = 25 * 1024 * 1024


def _clean(text: str) -> str:
    """移除 NUL 與其他控制字元（保留 \\t \\n \\r），避免下游 subprocess/LLM 出錯。"""
    return _CONTROL_CHARS.sub("", text or "")


def extract_text(data: bytes, filename: str) -> str:
    """依副檔名抽取純文字；未知副檔名以 UTF-8 文字處理。輸出一律清掉控制字元。"""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        raw = _extract_pdf(data)
    elif name.endswith(".docx"):
        raw = _extract_docx(data)
    else:
        raw = data.decode("utf-8", errors="ignore")
    return _clean(raw)


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for idx, page in enumerate(reader.pages):
        if idx >= MAX_PDF_PAGES:
            break
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _extract_docx(data: bytes) -> str:
    from docx import Document

    try:
        with ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            expanded_bytes = sum(entry.file_size for entry in entries)
            if len(entries) > MAX_DOCX_ENTRIES or expanded_bytes > MAX_DOCX_EXPANDED_BYTES:
                raise ValueError("DOCX expanded content is too large")
    except BadZipFile as exc:
        raise ValueError("invalid DOCX file") from exc
    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs).strip()
