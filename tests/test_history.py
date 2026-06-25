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


def test_create_running_then_update_result():
    # 背景流程：先建『進行中』佔位（有暫時標題、profile），跑完補成品並轉 done。
    pid = history.create_running_package("t-run", "AI 工程師 JD", "AI 工程師", {"name": "王"})
    row = next(r for r in history.list_packages() if r["id"] == pid)
    assert row["status"] == "running" and row["job_title"] == "AI 工程師"
    assert history.get_package(pid)["profile"]["name"] == "王"  # 建立時就存 profile
    history.update_package_result(pid, _state())
    row = next(r for r in history.list_packages() if r["id"] == pid)
    assert row["status"] == "done" and row["company"] == "未來智能" and row["match_score"] == 82
    full = history.get_package(pid)
    assert full["package"]["tailored_resume"]["summary"] == "後端"
    assert full["profile"]["name"] == "王"  # update 不覆蓋建立時存的 profile


def test_set_status_marks_failed():
    pid = history.create_running_package("t-x", "JD", "T", None)
    history.set_status(pid, "failed")
    assert next(r for r in history.list_packages() if r["id"] == pid)["status"] == "failed"


def test_mark_stale_running_failed_on_startup():
    # 伺服器重啟時殘留的 running 應被收尾為 failed（不會永遠卡進行中）。
    pid = history.create_running_package("t-stale", "JD", "卡住的", None)
    assert next(r for r in history.list_packages() if r["id"] == pid)["status"] == "running"
    history.mark_stale_running_failed()
    assert next(r for r in history.list_packages() if r["id"] == pid)["status"] == "failed"


def test_set_approved_updates_status():
    # 批次產生的待審包，事後在「我的投遞包」核可 → approved 由 0 變 1。
    s = _state()
    s["approved"] = None  # 模擬批次存檔（待審）
    pid = history.save_package(s)
    assert next(r for r in history.list_packages() if r["id"] == pid)["approved"] == 0
    history.set_approved(pid, True)
    assert next(r for r in history.list_packages() if r["id"] == pid)["approved"] == 1


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
