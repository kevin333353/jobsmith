import pytest

from app.intake import jd_fetch


def test_extracts_104_via_api(monkeypatch):
    fake = {"data": {
        "header": {"jobName": "資深 AI 工程師", "custName": "未來智能股份有限公司"},
        "jobDetail": {
            "jobDescription": "負責設計與開發多 agent LLM 系統，串接 RAG 與工具呼叫。",
            "salary": "月薪 70,000~100,000 元",
        },
        "condition": {
            "specialty": [{"description": "Python"}, {"description": "LangGraph"}],
            "other": "具 LLM 專案經驗者佳。",
        },
    }}
    monkeypatch.setattr(jd_fetch, "_http_json", lambda url, referer: fake)
    res = jd_fetch.fetch_jd("https://www.104.com.tw/job/abcXYZ?jobsource=x")
    assert res.source == "104"
    assert res.title == "資深 AI 工程師"
    assert "未來智能" in res.company
    assert "多 agent" in res.text
    assert "Python" in res.text  # 需求技能併入內文


def test_extracts_generic_html(monkeypatch):
    html = """<html><head><title>AI Engineer - Acme</title></head>
    <body><script>var secret=1;</script><nav>選單</nav>
    <main><h1>AI Engineer</h1>
    <p>We are hiring an AI engineer to build multi-agent systems with Python;
    strong LLM and RAG experience is required for this senior role.</p></main>
    <footer>copyright 2026</footer></body></html>"""
    monkeypatch.setattr(jd_fetch, "_http_html", lambda url: html)
    res = jd_fetch.fetch_jd("https://example.com/jobs/123")
    assert res.source == "web"
    assert "multi-agent" in res.text
    assert "var secret" not in res.text   # script 已移除
    assert "copyright" not in res.text    # footer 已移除


def test_too_short_raises(monkeypatch):
    monkeypatch.setattr(jd_fetch, "_http_html",
                        lambda url: "<html><body><main>太短</main></body></html>")
    with pytest.raises(jd_fetch.JDFetchError):
        jd_fetch.fetch_jd("https://example.com/x")


def test_invalid_url_raises():
    with pytest.raises(jd_fetch.JDFetchError):
        jd_fetch.fetch_jd("not-a-url")


def test_network_error_wrapped(monkeypatch):
    def boom(url):
        raise RuntimeError("connection reset")
    monkeypatch.setattr(jd_fetch, "_http_html", boom)
    with pytest.raises(jd_fetch.JDFetchError):
        jd_fetch.fetch_jd("https://example.com/x")


def test_blocks_loopback_ssrf():
    # SSRF 防護：loopback 位址在發出任何請求前就被擋（_guard_host 走真實 getaddrinfo）
    with pytest.raises(jd_fetch.JDFetchError):
        jd_fetch.fetch_jd("http://127.0.0.1:8000/admin")


def test_blocks_cloud_metadata_ssrf():
    # link-local 169.254.169.254（雲端 metadata）必須被擋
    with pytest.raises(jd_fetch.JDFetchError):
        jd_fetch.fetch_jd("http://169.254.169.254/latest/meta-data/")
