from app.sources import source_104, source_yourator, source_cake, source_linkedin


class FakeResp:
    def __init__(self, ok=True, status=200, json_data=None, text=""):
        self.ok = ok
        self.status_code = status
        self._json = json_data
        self.text = text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def test_source_104_parses(monkeypatch):
    payload = {"data": [{
        "jobName": "[[[AI]]]工程師", "custName": "未來智能", "jobAddrNoDesc": "台北",
        "salaryDesc": "面議", "descSnippet": "做 [[[Python]]] 開發",
        "link": {"job": "https://www.104.com.tw/job/abc"},
    }]}
    monkeypatch.setattr(source_104, "http_get", lambda *a, **k: FakeResp(json_data=payload))
    res = source_104.search("AI", limit=5)
    assert res.blocked is False
    assert len(res.jobs) == 1
    j = res.jobs[0]
    assert j.title == "AI工程師"          # [[[ ]]] 已清除
    assert j.company == "未來智能"
    assert j.url.endswith("/abc")
    assert "Python" in j.snippet and "[[[" not in j.snippet


def test_source_104_paginates_and_dedups(monkeypatch):
    # pages=2：抓兩頁、合併、跨頁去重（job/1 在兩頁都出現，只計一次）
    pages_data = {
        "1": {"data": [
            {"jobName": "A", "custName": "C", "link": {"job": "https://x/1"}},
            {"jobName": "B", "custName": "C", "link": {"job": "https://x/2"}},
        ]},
        "2": {"data": [
            {"jobName": "A", "custName": "C", "link": {"job": "https://x/1"}},  # 重複
            {"jobName": "D", "custName": "C", "link": {"job": "https://x/3"}},
        ]},
    }
    calls = []

    def fake_get(url, **k):
        # 從 URL 取出 page=N
        page = url.split("page=")[1].split("&")[0]
        calls.append(page)
        return FakeResp(json_data=pages_data[page])

    monkeypatch.setattr(source_104, "http_get", fake_get)
    res = source_104.search("AI", limit=15, pages=2)
    assert calls == ["1", "2"]                       # 真的抓了兩頁
    urls = [j.url for j in res.jobs]
    assert urls == ["https://x/1", "https://x/2", "https://x/3"]  # 去重後 3 筆


def test_source_104_pages_default_one(monkeypatch):
    # 預設 pages=1 只抓第一頁（維持舊行為）
    calls = []

    def fake_get(url, **k):
        calls.append(url)
        return FakeResp(json_data={"data": [{"jobName": "A", "custName": "C",
                                             "link": {"job": "https://x/1"}}]})

    monkeypatch.setattr(source_104, "http_get", fake_get)
    source_104.search("AI")
    assert len(calls) == 1


def test_source_104_salary_from_low_high(monkeypatch):
    # 真實 104 回傳：salaryDesc 不存在，數值在 salaryLow/salaryHigh + 型態碼 s10
    payload = {"data": [
        {"jobName": "月薪職", "custName": "A", "salaryLow": 48000, "salaryHigh": 70000,
         "s10": 50, "link": {"job": "https://x/1"}},
        {"jobName": "年薪職", "custName": "B", "salaryLow": 800000, "salaryHigh": 1300000,
         "s10": 60, "link": {"job": "https://x/2"}},
        {"jobName": "面議職", "custName": "C", "salaryLow": 0, "salaryHigh": 0,
         "s10": 10, "link": {"job": "https://x/3"}},
    ]}
    monkeypatch.setattr(source_104, "http_get", lambda *a, **k: FakeResp(json_data=payload))
    res = source_104.search("AI", limit=5)
    salaries = [j.salary for j in res.jobs]
    assert salaries[0] == "月薪 NT$48,000–70,000"
    assert salaries[1] == "年薪 NT$800,000–1,300,000"
    assert salaries[2] == "面議"


def test_source_104_open_ended_salary_sentinel(monkeypatch):
    # 104「X 元以上」回傳 salaryHigh=9999999 哨兵值，不可印成 NT$40,000–9,999,999
    payload = {"data": [{"jobName": "x", "custName": "A", "salaryLow": 40000,
                         "salaryHigh": 9999999, "s10": 50, "link": {"job": "https://x/1"}}]}
    monkeypatch.setattr(source_104, "http_get", lambda *a, **k: FakeResp(json_data=payload))
    j = source_104.search("AI").jobs[0]
    assert j.salary == "月薪 NT$40,000 以上"


def test_source_104_ignores_legacy_salarydesc(monkeypatch):
    # 即使有舊的 salaryDesc 字串也不再採用，一律以 low/high 計算
    payload = {"data": [{"jobName": "x", "custName": "A", "salaryDesc": "舊字串",
                         "salaryLow": 40000, "salaryHigh": 50000, "s10": 50,
                         "link": {"job": "https://x/1"}}]}
    monkeypatch.setattr(source_104, "http_get", lambda *a, **k: FakeResp(json_data=payload))
    j = source_104.search("AI").jobs[0]
    assert j.salary == "月薪 NT$40,000–50,000"


def test_source_104_blocked_on_error(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("nope")
    monkeypatch.setattr(source_104, "http_get", boom)
    res = source_104.search("AI")
    assert res.blocked is True and res.jobs == []


def test_source_104_blocked_on_non_ok(monkeypatch):
    monkeypatch.setattr(source_104, "http_get", lambda *a, **k: FakeResp(ok=False, status=403))
    res = source_104.search("AI")
    assert res.blocked is True and res.error == "HTTP 403"


def test_source_yourator_parses(monkeypatch):
    payload = {"payload": {"jobs": [{
        "name": "AI 工程師", "location": "台北市", "salary": "NT$ 40,000",
        "path": "/companies/x/jobs/1", "tags": ["AI", "Python"],
        "company": {"brand": "某公司"},
    }]}}
    monkeypatch.setattr(source_yourator, "http_get", lambda *a, **k: FakeResp(json_data=payload))
    res = source_yourator.search("AI")
    assert len(res.jobs) == 1
    j = res.jobs[0]
    assert j.company == "某公司"
    assert j.url == "https://www.yourator.co/companies/x/jobs/1"
    assert "Python" in j.requirements


def test_source_cake_blocked_when_no_next_data(monkeypatch):
    monkeypatch.setattr(source_cake, "http_get", lambda *a, **k: FakeResp(text="<html>no data</html>"))
    res = source_cake.search("AI")
    assert res.blocked is True


_CAKE_HTML = """<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"initialState":{"jobSearch":{"entityByPathId":{
"ai-engineer-1":{"path":"ai-engineer-1","title":"AI Engineer","description":"Build LLM systems",
"locations":["台北市, 台灣"],"salary":{"min":"1500000","max":"2100000","currency":"TWD","type":"per_year"},
"tags":["Python","LLM"],"page":{"path":"swag","name":"SWAG"}}
}}}}}}
</script></body></html>"""


def test_source_cake_parses_entity_state(monkeypatch):
    monkeypatch.setattr(source_cake, "http_get", lambda *a, **k: FakeResp(text=_CAKE_HTML))
    res = source_cake.search("AI", limit=5)
    assert res.blocked is False
    assert len(res.jobs) == 1
    j = res.jobs[0]
    assert j.title == "AI Engineer"
    assert j.company == "SWAG"
    assert j.url == "https://www.cake.me/companies/swag/jobs/ai-engineer-1"
    assert j.salary == "年薪 TWD 1,500,000–2,100,000"
    assert j.location == "台北市, 台灣"
    assert "Python" in j.requirements


def test_source_cake_blocked_when_no_entities(monkeypatch):
    empty = ('<script id="__NEXT_DATA__" type="application/json">'
             '{"props":{"pageProps":{"initialState":{"jobSearch":{"entityByPathId":{}}}}}}</script>')
    monkeypatch.setattr(source_cake, "http_get", lambda *a, **k: FakeResp(text=empty))
    assert source_cake.search("AI").blocked is True


_LI_HTML = """
<ul>
  <li><div class="base-card">
    <a class="base-card__full-link" href="https://tw.linkedin.com/jobs/view/ai-engineer-123?refId=x&trackingId=y">l</a>
    <h3 class="base-search-card__title">  AI Engineer  </h3>
    <h4 class="base-search-card__subtitle">Onramp Lab</h4>
    <span class="job-search-card__location">Taipei City, Taiwan</span>
  </div></li>
  <li><div class="base-card">
    <a class="base-card__full-link" href="https://tw.linkedin.com/jobs/view/ml-eng-456">l</a>
    <h3 class="base-search-card__title">ML Engineer</h3>
    <h4 class="base-search-card__subtitle">Acme</h4>
    <span class="job-search-card__location">Taiwan</span>
  </div></li>
</ul>
"""


def test_source_linkedin_parses(monkeypatch):
    monkeypatch.setattr(source_linkedin, "http_get", lambda *a, **k: FakeResp(text=_LI_HTML))
    res = source_linkedin.search("AI", limit=5)
    assert res.blocked is False
    assert len(res.jobs) == 2
    j = res.jobs[0]
    assert j.title == "AI Engineer"
    assert j.company == "Onramp Lab"
    assert j.location == "Taipei City, Taiwan"
    assert j.url == "https://tw.linkedin.com/jobs/view/ai-engineer-123"  # query 已去除
    assert j.source == "linkedin"


def test_source_linkedin_blocked_on_empty(monkeypatch):
    monkeypatch.setattr(source_linkedin, "http_get", lambda *a, **k: FakeResp(text="<html></html>"))
    assert source_linkedin.search("AI").blocked is True


def test_source_linkedin_blocked_on_error(monkeypatch):
    def boom(*a, **k):
        raise ConnectionError("nope")
    monkeypatch.setattr(source_linkedin, "http_get", boom)
    assert source_linkedin.search("AI").blocked is True


def test_registry_search_all_aggregates(monkeypatch):
    from app.sources import registry
    from app.models import SearchResult
    monkeypatch.setattr(registry, "SEARCHABLE", {
        "104": lambda kw, limit=15, pages=1: SearchResult(source="104"),
        "yourator": lambda kw, limit=15, pages=1: SearchResult(source="yourator"),
    })
    results = registry.search_all("AI")
    assert [r.source for r in results] == ["104", "yourator"]


def test_registry_search_all_passes_pages(monkeypatch):
    """search_all 應把 pages 下傳給各來源。"""
    from app.sources import registry
    from app.models import SearchResult
    seen = {}

    def fake(kw, limit=15, pages=1):
        seen["pages"] = pages
        return SearchResult(source="104")

    monkeypatch.setattr(registry, "SEARCHABLE", {"104": fake})
    registry.search_all("AI", pages=3)
    assert seen["pages"] == 3


def test_linkedin_search_url():
    from app.sources.registry import linkedin_search_url
    url = linkedin_search_url("AI 工程師")
    assert url.startswith("https://www.linkedin.com/jobs/search/")
    assert "Taiwan" in url
