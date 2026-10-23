"""全局输出语言：页面切换写入 `<data_cache_dir>/ui_settings.json`，所有后端文字按它出中文或英文。

用法：
    from analyst.i18n import L, is_en
    title = L("触及支撑", "Touched support")
    msg = L(f"现价 {px}", f"Price {px}")

只换给人看的文字；规则名、枚举、dict key、JSON 字段名不随语言变。
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

SUPPORTED = ("zh", "en")

_lock = threading.Lock()
_lang: str | None = None
_explicit = False
_override: str | None = None


def normalize(lang: str | None) -> str:
    return "en" if str(lang or "").strip().lower().startswith("en") else "zh"


def _settings_file() -> Path:
    from analyst.config import get_settings

    return get_settings().cache_path / "ui_settings.json"


def _load() -> None:
    global _lang, _explicit
    lang, explicit = normalize(os.environ.get("UI_LANG") or "zh"), False
    try:
        data = json.loads(_settings_file().read_text(encoding="utf-8"))
        if data.get("lang") in SUPPORTED:
            lang, explicit = data["lang"], True
    except (OSError, ValueError):
        pass
    _lang, _explicit = lang, explicit


def get_lang() -> str:
    if _override is not None:
        return _override
    with _lock:
        if _lang is None:
            _load()
        return _lang or "zh"


def is_explicit() -> bool:
    get_lang()
    return _explicit


def set_lang(lang: str) -> str:
    """持久化并立即生效。"""
    global _lang, _explicit
    v = normalize(lang)
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        data["lang"] = v
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _lang, _explicit = v, True
    return v


def force_lang(lang: str | None) -> None:
    """进程内覆盖、不落盘（测试用；None 取消）。"""
    global _override
    _override = normalize(lang) if lang is not None else None


def is_en() -> bool:
    return get_lang() == "en"


def L(zh: str, en: str) -> str:
    return en if is_en() else zh
