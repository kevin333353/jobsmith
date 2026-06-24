"""貼 JD 網址自動抓取：104 走官方 job content API（品質最佳），其他站走通用 HTML 抽取。

104 職缺頁是 JS 渲染，直接抓 HTML 無內容，故偵測 job id 改打官方 content API；
通用網址用 BeautifulSoup 取主文（移除 script/nav/footer 等雜訊）。失敗一律拋 JDFetchError，
由端點轉成友善訊息，請使用者改貼 JD 文字。

安全：URL 由使用者提供 → server 端抓取屬 SSRF 面向。抓取前解析主機 IP，擋掉
loopback / 內網 / link-local（含雲端 metadata 169.254.169.254）/ reserved；redirect
逐跳重新驗證；回應設大小上限避免被超大內容打爆記憶體。
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

from app.sources.base import UA, clean

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


def _guard_host(url: str) -> None:
    """解析主機所有 IP，擋掉 loopback/內網/link-local/reserved（防 SSRF）。"""
    host = urlparse(url).hostname
    if not host:
        raise JDFetchError("無效的網址。")
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception as exc:
        raise JDFetchError("無法解析網址主機。") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            raise JDFetchError("基於安全考量，不允許抓取內部或保留位址。")


def _guarded_read(url: str, referer: str | None, accept: str) -> tuple[bytes, str]:
    """逐跳驗證主機 + 串流讀取設大小上限，回 (content, encoding)。"""
    headers = {"User-Agent": UA, "Accept": accept}
    if referer:
        headers["Referer"] = referer
    cur, hops = url, 0
    while True:
        _guard_host(cur)
        with httpx.stream("GET", cur, headers=headers, timeout=20, follow_redirects=False) as r:
            if r.is_redirect and r.headers.get("location") and hops < _MAX_REDIRECTS:
                cur = urljoin(cur, r.headers["location"])
                hops += 1
                continue
            r.raise_for_status()
            total, chunks = 0, []
            for chunk in r.iter_bytes():
                total += len(chunk)
                if total > _MAX_BYTES:
                    raise JDFetchError("回應內容過大，已中止抓取。")
                chunks.append(chunk)
            return b"".join(chunks), (r.encoding or "utf-8")


def _http_json(url: str, referer: str) -> dict:
    content, _ = _guarded_read(url, referer, "application/json")
    return json.loads(content)


def _http_html(url: str) -> str:
    content, enc = _guarded_read(url, None, "text/html,application/xhtml+xml")
    return content.decode(enc, errors="replace")


def _fetch_104(jid: str) -> JDFetchResult:
    data = _http_json(_104_CONTENT.format(jid=jid),
                      referer=f"https://www.104.com.tw/job/{jid}").get("data") or {}
    header = data.get("header") or {}
    detail = data.get("jobDetail") or {}
    cond = data.get("condition") or {}
    title = clean(header.get("jobName") or "")
    company = clean(header.get("custName") or "")
    skills = "、".join(
        s.get("description", "") for s in (cond.get("specialty") or []) if s.get("description"))
    parts = [
        detail.get("jobDescription") or "",
        f"工作待遇：{detail.get('salary')}" if detail.get("salary") else "",
        f"需求技能：{skills}" if skills else "",
        cond.get("other") or "",
    ]
    text = clean("\n".join(p for p in parts if p))
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
