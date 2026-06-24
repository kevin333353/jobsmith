from io import BytesIO

from docx import Document

from app.export.docx_export import build_docx


def test_build_docx_returns_valid_zip():
    data = build_docx({
        "job_title": "AI 工程師",
        "resume": {"summary": "後端工程師", "bullets": ["建多 agent 系統"]},
    })
    assert isinstance(data, bytes) and len(data) > 0
    assert data[:2] == b"PK"  # docx 本質是 zip


def test_docx_contains_text():
    data = build_docx({
        "job_title": "AI 工程師", "company": "未來智能",
        "resume": {"summary": "資深後端", "bullets": ["建立 RAG 管線"]},
        "cover_letter": {"subject": "應徵 AI 工程師", "body": "您好\n我對貴公司很有興趣。"},
        "interview": {"technical_questions": ["介紹一次系統設計經驗"]},
    })
    doc = Document(BytesIO(data))
    full = "\n".join(p.text for p in doc.paragraphs)
    assert "資深後端" in full
    assert "RAG" in full
    assert "貴公司" in full
    assert "系統設計" in full


def test_build_docx_empty_pkg():
    data = build_docx({})
    assert data[:2] == b"PK"  # 空包也要產出有效檔，不丟例外


def test_build_docx_tolerates_bad_shapes():
    # 子欄位非 dict（前端可能送錯/被編輯成奇怪形狀）→ 不拋例外，仍產出有效檔
    data = build_docx({
        "job_title": ["不是字串"],
        "resume": "其實是字串",
        "cover_letter": [],
        "interview": None,
    })
    assert data[:2] == b"PK"
