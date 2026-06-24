from app.store import history


def _state():
    return {"jd_text": "AI 工程師 JD", "profile": {"name": "王", "raw_text": "x"},
            "parsed_job": {"title": "AI 工程師", "company": "未來智能"},
            "match_report": {"score": 82},
            "tailored_resume": {"summary": "後端", "bullets": ["建 RAG"]},
            "cover_letter": {"subject": "應徵", "body": "您好"},
            "interview_kit": {"technical_questions": ["q"]},
            "critique": {"overall_pass": True}, "approved": True}


def test_save_list_get():
    pid = history.save_package(_state())
    rows = history.list_packages()
    row = next(r for r in rows if r["id"] == pid)
    assert row["company"] == "未來智能" and row["match_score"] == 82
    full = history.get_package(pid)
    assert full["package"]["tailored_resume"]["summary"] == "後端"
    assert full["profile"]["name"] == "王"


def test_delete():
    pid = history.save_package(_state())
    history.delete_package(pid)
    assert history.get_package(pid) is None


def test_get_missing_returns_none():
    assert history.get_package(999999) is None


def test_save_is_idempotent_per_thread_id():
    # 同一 thread_id 重存（resume 重送/雙擊）只應留一筆，回傳同一 id。
    pid1 = history.save_package(_state(), thread_id="t-abc")
    pid2 = history.save_package(_state(), thread_id="t-abc")
    assert pid1 == pid2
    same = [r for r in history.list_packages() if r["id"] == pid1]
    assert len(same) == 1


def test_save_without_thread_id_still_inserts_each_time():
    # 沒帶 thread_id 時維持原行為（每次都插入新列）。
    a = history.save_package(_state())
    b = history.save_package(_state())
    assert a != b
