"""貼 JD 網址自動抓取：104 走官方 job content API（品質最佳），其他站走通用 HTML 抽取。

104 職缺頁是 JS 渲染，直接抓 HTML 無內容，故偵測 job id 改打官方 content API；
通用網址用 BeautifulSoup 取主文（移除 script/nav/footer 等雜訊）。失敗一律拋 JDFetchError，
由端點轉成友善訊息，請使用者改貼 JD 文字。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.sources.base import UA, clean

_104_JOB = re.compile(r"104\.com\.tw/job/(\w+)")
_104_CONTENT = "https://www.104.com.tw/job/ajax/content/{jid}"
_MIN_LEN = 60
_MAX_TEXT = 8000  # 控制送進 LLM 的長度


class JDFetchError(Exception):
    """抓取失敗或內容過短，請使用者改貼 JD 文字。"""


@dataclass
class JDFetchResult:
    title: str
    company: str
    text: str
    source: str


def _http_json(url: str, referer: str) -> dict:
    headers = {"User-Agent": UA, "Referer": referer, "Accept": "application/json"}
    r = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
    r.raise_for_status()
    return r.json()


def _http_html(url: str) -> str:
    headers = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"}
    r = httpx.get(url, headers=headers, timeout=20, follow_redirects=True)
    r.raise_for_status()
    return r.text


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
