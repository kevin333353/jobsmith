from app.store import searches


def _payload():
    return {
        "jobs": [{"job": {"title": "AI 工程師"}, "fit_score": 88}],
        "companyJobs": [],
        "skillGap": {"top_demand": []},
        "queries": ["AI 工程師"],
    }


def test_save_list_get_delete():
    sid = searches.save_search("徐凱瑞的搜尋", {"name": "徐凱瑞"}, _payload())
    rows = searches.list_searches()
    row = next(r for r in rows if r["id"] == sid)
    assert row["label"] == "徐凱瑞的搜尋"
    assert row["ai_count"] == 1 and row["company_count"] == 0
    full = searches.get_search(sid)
    assert full["payload"]["queries"] == ["AI 工程師"]
    assert full["profile"]["name"] == "徐凱瑞"
    searches.delete_search(sid)
    assert searches.get_search(sid) is None


def test_get_missing_returns_none():
    assert searches.get_search(987654) is None
