"""Prompt 模板加载与渲染。

Prompts 单独放在 prompts/ 目录下，每个版本独立文件，方便 A/B 测试。
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent.parent.parent.parent / "prompts"


def load_system_prompt(version: str = "v1") -> str:
    """加载系统提示词。"""
    path = PROMPTS_DIR / f"system_{version}.md"
    return path.read_text(encoding="utf-8")


def load_user_template(version: str = "v1") -> str:
    """加载用户消息模板（带 {placeholders}）。"""
    path = PROMPTS_DIR / f"user_template_{version}.md"
    return path.read_text(encoding="utf-8")


def render_user_message(template: str, **kwargs) -> str:
    """渲染用户消息（简单 format 替换）。"""
    return template.format(**kwargs)


SUPPORTED_LANGS = ("zh", "en")


def normalize_lang(lang: str | None) -> str:
    """界面语言归一化：只认 zh / en，其余按 zh。"""
    x = (lang or "").strip().lower()
    return "en" if x.startswith("en") else "zh"


def language_directive(lang: str | None) -> str:
    """追加在用户消息末尾的输出语言要求；中文为默认，不追加。"""
    if normalize_lang(lang) != "en":
        return ""
    return (
        "\n\n## Output language\n"
        "Write every free-text field (rationale, notes, replies) in English. "
        "Keep the 【section】 markers but translate the section titles into English. "
        "Field names, enum values (long/short/wait) and numbers stay unchanged."
    )
