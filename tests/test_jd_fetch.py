import pytest

from app.intake import jd_fetch


class _FakeResp:
    ok = True
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_extracts_104_via_api(monkeypatch):
    payload = {"data": {
        "header": {"jobName": "資深 AI 工程師", "custName": "未來智能股份有限公司"},
        "jobDetail": {
            "jobDescription": "負責設計與開發多 agent LLM 系統，串接 RAG 與工具呼叫。",
            "salary": "月薪 70,000~100,000 元",
            "jobCategory": [{"description": "軟體工程師"}],
        },
        "condition": {
            "workExp": "2年以上",
            "edu": "大學以上",
            "major": ["資訊工程相關"],
            "language": [{"language": "英文"}],
            "specialty": [{"description": "Python"}, {"description": "LangGraph"}],
            "skill": [{"description": "LLM 應用"}],
            "other": "具 LLM 專案經驗者佳。",
        },
    }}
    monkeypatch.setattr(jd_fetch, "http_get", lambda url, referer=None: _FakeResp(payload))
    res = jd_fetch.fetch_jd("https://www.104.com.tw/job/abcXYZ?jobsource=x")
    assert res.source == "104"
    assert res.title == "資深 AI 工程師"
    assert "未來智能" in res.company
    assert "多 agent" in res.text
    assert "Python" in res.text                       # 擅長工具
    assert "2年以上" in res.text and "大學以上" in res.text  # 條件要求併入
    assert "資訊工程相關" in res.text                  # 科系要求併入


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


def test_blocks_non_global_shared_address_ssrf(monkeypatch):
    def fake_getaddrinfo(host, port, *args, **kwargs):
        return [(
            jd_fetch.socket.AF_INET,
            jd_fetch.socket.SOCK_STREAM,
            jd_fetch.socket.IPPROTO_TCP,
            "",
            ("100.64.0.1", 0),
        )]

    monkeypatch.setattr(jd_fetch.socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(jd_fetch.JDFetchError, match="安全"):
        jd_fetch._guard_host("http://jobs.example.test/posting")


def test_guarded_read_pins_validated_address(monkeypatch):
    seen = {}
    public_ip = "93.184.216.34"

    def fake_getaddrinfo(host, port, *args, **kwargs):
        assert host == "jobs.example.test"
        return [(
            jd_fetch.socket.AF_INET,
            jd_fetch.socket.SOCK_STREAM,
            jd_fetch.socket.IPPROTO_TCP,
            "",
            (public_ip, 0),
        )]

    class FakeResponse:
        is_redirect = False
        headers = {}
        encoding = "utf-8"

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            yield b"synthetic job description"

    class FakeClient:
        def __init__(self, **kwargs):
            seen["client_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, **kwargs):
            seen["method"] = method
            seen["url"] = url
            seen["stream_kwargs"] = kwargs
            return FakeResponse()

    def fail_unpinned_request(*args, **kwargs):
        pytest.fail("request used the original hostname instead of the validated IP")

    monkeypatch.setattr(jd_fetch.socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(jd_fetch.httpx, "stream", fail_unpinned_request)
    monkeypatch.setattr(jd_fetch.httpx, "Client", FakeClient)

    content, encoding = jd_fetch._guarded_read(
        "https://jobs.example.test/posting?id=7",
        None,
        "text/html",
    )

    assert content == b"synthetic job description"
    assert encoding == "utf-8"
    assert seen["client_kwargs"]["trust_env"] is False
    assert jd_fetch.httpx.URL(seen["url"]).host == public_ip
    assert seen["stream_kwargs"]["headers"]["Host"] == "jobs.example.test"
    assert seen["stream_kwargs"]["extensions"]["sni_hostname"] == "jobs.example.test"
