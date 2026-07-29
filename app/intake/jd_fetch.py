"""貼 JD 網址自動抓取：104 走官方 job content API（品質最佳），其他站走通用 HTML 抽取。

104 職缺頁是 JS 渲染，直接抓 HTML 無內容，故偵測 job id 改打官方 content API；
通用網址用 BeautifulSoup 取主文（移除 script/nav/footer 等雜訊）。失敗一律拋 JDFetchError，
由端點轉成友善訊息，請使用者改貼 JD 文字。

安全：URL 由使用者提供 → server 端抓取屬 SSRF 面向。抓取前解析主機全部 IP，只允許
全球公開位址，並把實際連線鎖定至已驗證 IP（保留原 Host/TLS SNI）；redirect 逐跳重新
驗證；回應設大小上限避免被超大內容打爆記憶體。
"""
from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.sources.base import UA, clean, http_get

_104_JOB = re.compile(r"104\.com\.tw/job/(\w+)")
_104_CONTENT = "https://www.104.com.tw/job/ajax/content/{jid}"
_MIN_LEN = 60
_MAX_TEXT = 8000        # 控制送進 LLM 的長度
_MAX_BYTES = 5_000_000  # 單次抓取回應大小上限（防 OOM）
_MAX_REDIRECTS = 4


class JDFetchError(Exception):
    """抓取失敗或內容過短，請使用者改貼 JD 文字。"""


@dataclass
class JDFetchResult:
    title: str
    company: str
    text: str
    source: str


def _guard_host(url: str) -> tuple[str, ...]:
    """解析並回傳主機的全球公開 IP；任一非公開位址即拒絕（防 SSRF）。"""
    parsed = urlparse(url)
    host = parsed.hostname
    if parsed.scheme not in ("http", "https") or not host:
        raise JDFetchError("無效的網址。")
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except Exception as exc:
        raise JDFetchError("無法解析網址主機。") from exc

    addresses: list[str] = []
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError as exc:
            raise JDFetchError("無法解析網址主機。") from exc
        if not ip.is_global:
            raise JDFetchError("基於安全考量，不允許抓取內部或保留位址。")
        normalized = str(ip)
        if normalized not in addresses:
            addresses.append(normalized)
    if not addresses:
        raise JDFetchError("無法解析網址主機。")
    return tuple(addresses)


def _guarded_read(url: str, referer: str | None, accept: str) -> tuple[bytes, str]:
    """逐跳驗證並鎖定已驗證 IP；串流讀取設大小上限，回 (content, encoding)。"""
    headers = {"User-Agent": UA, "Accept": accept}
    if referer:
        headers["Referer"] = referer
    cur, hops = url, 0
    while True:
        addresses = _guard_host(cur)
        original = httpx.URL(cur)
        host_header = original.netloc.decode("ascii")
        sni_hostname = original.raw_host.decode("ascii")
        redirect_url: str | None = None
        last_connect_error: Exception | None = None

        # 每一跳使用獨立 client，避免不同原始 host 共用同一個「IP origin」TLS 連線。
        with httpx.Client(trust_env=False, follow_redirects=False) as client:
            for address in addresses:
                pinned_url = original.copy_with(host=address)
                request_headers = {**headers, "Host": host_header}
                try:
                    with client.stream(
                        "GET",
                        pinned_url,
                        headers=request_headers,
                        timeout=20,
                        follow_redirects=False,
                        extensions={"sni_hostname": sni_hostname},
                    ) as r:
                        if (r.is_redirect and r.headers.get("location")
                                and hops < _MAX_REDIRECTS):
                            redirect_url = urljoin(cur, r.headers["location"])
                            break
                        r.raise_for_status()
                        total, chunks = 0, []
                        for chunk in r.iter_bytes():
                            total += len(chunk)
                            if total > _MAX_BYTES:
                                raise JDFetchError("回應內容過大，已中止抓取。")
                            chunks.append(chunk)
                        return b"".join(chunks), (r.encoding or "utf-8")
                except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                    last_connect_error = exc

        if redirect_url is not None:
            cur = redirect_url
            hops += 1
            continue
        if last_connect_error is not None:
            raise last_connect_error
        raise JDFetchError("無法連線至網址主機。")


def _http_json(url: str, referer: str) -> dict:
    content, _ = _guarded_read(url, referer, "application/json")
    return json.loads(content)


def _http_html(url: str) -> str:
    content, enc = _guarded_read(url, None, "text/html,application/xhtml+xml")
    return content.decode(enc, errors="replace")


def _s(x) -> str:
    """只取字串值（避免把 dict/list 直接塞進 JD 變亂碼）。"""
    return clean(x) if isinstance(x, str) else ""


def _descs(items) -> str:
    """list[{description}] → 頓號串接（職務類別/擅長工具/工作技能）。"""
    if not isinstance(items, list):
        return ""
    return "、".join(clean(i.get("description", "")) for i in items
                    if isinstance(i, dict) and i.get("description"))


def _langs(items) -> str:
    if not isinstance(items, list):
        return ""
    return "、".join(clean(i.get("language", "")) for i in items
                    if isinstance(i, dict) and i.get("language"))


def _addr(detail: dict) -> str:
    return clean("".join(_s(detail.get(k)) for k in ("addressRegion", "addressArea", "addressDetail")))


def _format_104(detail: dict, cond: dict) -> str:
    """組出完整 JD：工作內容 + 工作條件 + 條件要求（盡量貼近 104 頁面分區）。"""
    majors = "、".join(str(m) for m in cond.get("major")) if isinstance(cond.get("major"), list) else _s(cond.get("major"))
    rows = [
        ("【工作內容】", _s(detail.get("jobDescription"))),
        ("職務類別：", _descs(detail.get("jobCategory"))),
        ("工作待遇：", _s(detail.get("salary"))),
        ("工作性質：", _s(detail.get("jobType")) or _descs(detail.get("workType"))),
        ("上班地點：", _addr(detail)),
        ("管理責任：", _s(detail.get("manageResp"))),
        ("出差外派：", _s(detail.get("businessTrip"))),
        ("上班時段：", _s(detail.get("workPeriod"))),
        ("休假制度：", _s(detail.get("vacationPolicy"))),
        ("可上班日：", _s(detail.get("startWorkingDay"))),
        ("需求人數：", _s(detail.get("needEmp"))),
        ("\n【條件要求】", ""),
        ("工作經歷：", _s(cond.get("workExp"))),
        ("學歷要求：", _s(cond.get("edu"))),
        ("科系要求：", majors),
        ("語文條件：", _langs(cond.get("language"))),
        ("擅長工具：", _descs(cond.get("specialty"))),
        ("工作技能：", _descs(cond.get("skill"))),
        ("其他條件：", _s(cond.get("other"))),
    ]
    lines = []
    for label, val in rows:
        if label.startswith(("【", "\n【")):
            lines.append(f"{label}\n{val}".rstrip())
        elif val:
            lines.append(f"{label}{val}")
    return "\n".join(line for line in lines if line.strip())


def _fetch_104(jid: str) -> JDFetchResult:
    # 104 content 走 requests（與搜尋同一管道，httpx 會被回 403）；host 由我們寫死、jid 為 \w+，無 SSRF 風險。
    r = http_get(_104_CONTENT.format(jid=jid), referer=f"https://www.104.com.tw/job/{jid}")
    if not getattr(r, "ok", False):
        raise JDFetchError(f"104 內容讀取失敗（HTTP {getattr(r, 'status_code', '?')}），請改貼 JD 文字。")
    data = r.json().get("data") or {}
    header = data.get("header") or {}
    detail = data.get("jobDetail") or {}
    cond = data.get("condition") or {}
    title = clean(header.get("jobName") or "")
    company = clean(header.get("custName") or "")
    text = clean(_format_104(detail, cond))
    if len(text) < _MIN_LEN:
        raise JDFetchError("104 職缺內容過短或無法解析，請改貼 JD 文字。")
    return JDFetchResult(title=title, company=company, text=text[:_MAX_TEXT], source="104")


def _fetch_generic(url: str) -> JDFetchResult:
    soup = BeautifulSoup(_http_html(url), "html.parser")
    title = clean(soup.title.string if soup.title and soup.title.string else "")
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "form", "svg", "aside"]):
        tag.decompose()
    main = soup.find("main") or soup.body or soup
    text = main.get_text("\n", strip=True)
    text = clean(re.sub(r"\n{2,}", "\n", text))
    if len(text) < _MIN_LEN:
        raise JDFetchError("無法從該網址擷取足夠內容，請改貼 JD 文字。")
    return JDFetchResult(title=title[:120], company="", text=text[:_MAX_TEXT], source="web")


def fetch_jd(url: str) -> JDFetchResult:
    """從職缺網址抽取 JD：104 走官方 API，其餘走通用 HTML 抽取。失敗拋 JDFetchError。"""
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise JDFetchError("請輸入有效的網址（需以 http:// 或 https:// 開頭）。")
    m = _104_JOB.search(url)
    try:
        return _fetch_104(m.group(1)) if m else _fetch_generic(url)
    except JDFetchError:
        raise
    except Exception as exc:  # 網路/解析錯誤 → 統一轉友善錯誤
        raise JDFetchError(f"抓取失敗（{type(exc).__name__}），請改貼 JD 文字。") from exc
