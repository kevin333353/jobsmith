"""職缺來源共用工具：HTTP 取得、文字清理。

所有公開來源都使用系統／certifi 信任鏈驗證 TLS；憑證驗證失敗時該來源回 blocked，
不可降級成未驗證連線。各 source 失敗一律回 blocked，不拋例外。
"""
from __future__ import annotations

import re

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
TIMEOUT = 20

_HIGHLIGHT = re.compile(r"\[\[\[|\]\]\]")  # 104 關鍵字高亮標記


def clean(text: str | None) -> str:
    return _HIGHLIGHT.sub("", text or "").strip()


def http_get(url: str, *, referer: str | None = None, timeout: int = TIMEOUT):
    headers = {"User-Agent": UA, "Accept": "application/json, text/html"}
    if referer:
        headers["Referer"] = referer
    return requests.get(url, headers=headers, timeout=timeout)
