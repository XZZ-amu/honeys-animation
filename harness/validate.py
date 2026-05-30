#!/usr/bin/env python3
"""
validate.py — Honeys Animation 动画文件验证脚本
用法: python3 harness/validate.py animations/xxx.html
退出码: 0 = 全部通过, 1 = 有失败项
"""

import sys
import os
import re
from html.parser import HTMLParser


# ─────────────────────────────────────────────
# 颜色白名单（从 style-tokens.css 中提取）
# ─────────────────────────────────────────────
ALLOWED_COLORS = {
    "#ff8c00",  # --color-orange
    "#4169e1",  # --color-blue
    "#ff1493",  # --color-pink
    "#32cd32",  # --color-green
    "#adff2f",  # --color-lime
    "#f0f0f5",  # --color-bg
    "#999999",  # --color-structure（补全到 6 位）
    "#999",     # --color-structure（原始 3 位）
    "#cccccc",  # --color-structure-light（补全）
    "#ccc",     # --color-structure-light（原始）
    "#ffffff",  # 白色（常见中性色，结构需要）
    "#fff",
    "#000000",  # 黑色（常见中性色）
    "#000",
}

MAX_FILE_SIZE_BYTES = 200 * 1024  # 200KB

STYLE_TOKENS_PATH = os.path.join(
    os.path.dirname(__file__), "style-tokens.css"
)


# ─────────────────────────────────────────────
# 辅助工具
# ─────────────────────────────────────────────

def normalize_hex(color: str) -> str:
    """统一转成小写；把 3 位 hex 展开成 6 位。"""
    c = color.lower()
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        # 同时保留 3 位原始形式和展开形式
        return c
    return c


def expand_hex3(color: str) -> str:
    """把 #abc → #aabbcc，方便对比。"""
    c = color.lower()
    if re.fullmatch(r"#[0-9a-f]{3}", c):
        return "#" + c[1] * 2 + c[2] * 2 + c[3] * 2
    return c


def load_allowed_colors_from_tokens(path: str) -> set:
    """从 style-tokens.css 里提取所有 hex 颜色值，构建白名单。"""
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        css = f.read()
    found = set()
    for m in re.findall(r"#[0-9a-fA-F]{3,8}\b", css):
        norm = normalize_hex(m)
        found.add(norm)
        found.add(expand_hex3(m))  # 也加入展开形式
    return found


def extract_hex_colors_from_html(content: str) -> list:
    """从 HTML 内容中提取所有 #xxx / #xxxxxx 格式的颜色（去重后排序）。"""
    matches = re.findall(r"#([0-9a-fA-F]{3,8})\b", content)
    result = set()
    for m in matches:
        full = "#" + m
        if len(m) in (3, 6):  # 只关心 3 位和 6 位颜色
            result.add(full.lower())
    return sorted(result)


# ─────────────────────────────────────────────
# 检查函数
# ─────────────────────────────────────────────

class HTMLSyntaxChecker(HTMLParser):
    def __init__(self):
        super().__init__()
        self.errors = []

    def handle_error(self, message):
        self.errors.append(message)


def check_html_parseable(content: str) -> tuple:
    """检查 1：HTML 能否被解析器读取。"""
    checker = HTMLSyntaxChecker()
    try:
        checker.feed(content)
        # Python 的 HTMLParser 比较宽松，基本能 feed 就算通过
        # 额外检查：必须有 <html 或 <!DOCTYPE
        has_doctype = bool(re.search(r"<!DOCTYPE\s+html", content, re.IGNORECASE))
        has_html_tag = bool(re.search(r"<html[\s>]", content, re.IGNORECASE))
        has_body = bool(re.search(r"<body[\s>]", content, re.IGNORECASE))
        if not (has_doctype or has_html_tag or has_body):
            return False, "文件缺少基本 HTML 结构（<!DOCTYPE>/<html>/<body>）"
        return True, ""
    except Exception as e:
        return False, f"解析失败：{e}"


def check_animation_logic(content: str) -> tuple:
    """检查 2：有 Canvas 或动画逻辑。"""
    has_canvas = bool(re.search(r"<canvas[\s>]", content, re.IGNORECASE))
    has_raf = bool(re.search(r"requestAnimationFrame", content))
    has_css_anim = bool(re.search(r"animation\s*:", content, re.IGNORECASE))
    has_keyframes = bool(re.search(r"@keyframes", content, re.IGNORECASE))

    if has_canvas or has_raf or has_css_anim or has_keyframes:
        found = []
        if has_canvas: found.append("canvas")
        if has_raf: found.append("requestAnimationFrame")
        if has_css_anim: found.append("CSS animation")
        if has_keyframes: found.append("@keyframes")
        return True, f"发现：{', '.join(found)}"
    return False, "未找到 canvas、requestAnimationFrame、CSS animation 或 @keyframes"


def check_loop_mechanism(content: str) -> tuple:
    """检查 3：有循环机制。"""
    has_raf = bool(re.search(r"requestAnimationFrame", content))
    has_interval = bool(re.search(r"setInterval", content))
    has_infinite = bool(re.search(r"\binfinite\b", content, re.IGNORECASE))

    if has_raf or has_interval or has_infinite:
        found = []
        if has_raf: found.append("requestAnimationFrame")
        if has_interval: found.append("setInterval")
        if has_infinite: found.append("CSS infinite")
        return True, f"发现：{', '.join(found)}"
    return False, "未找到 requestAnimationFrame、setInterval 或 CSS infinite"


def check_colors(content: str, allowed: set) -> tuple:
    """检查 4：颜色合规。"""
    if not allowed:
        return "WARN", "无法读取 style-tokens.css，跳过颜色检查"

    found_colors = extract_hex_colors_from_html(content)
    if not found_colors:
        return "WARN", "HTML 中未找到任何 hex 颜色值，无法验证"

    violations = []
    for color in found_colors:
        norm = color.lower()
        expanded = expand_hex3(color)
        if norm not in allowed and expanded not in allowed:
            violations.append(color)

    if violations:
        return False, f"以下颜色不在白名单内：{', '.join(violations)}"
    return True, f"已检查 {len(found_colors)} 个颜色值，全部合规"


def check_no_forbidden_effects(content: str) -> tuple:
    """检查 5：无禁用效果。"""
    forbidden = [
        (r"\bshadowBlur\b",        "shadowBlur（Canvas 阴影模糊）"),
        (r"\bbox-shadow\b",        "box-shadow"),
        (r"\btext-shadow\b",       "text-shadow"),
        (r"\bfilter\s*:\s*blur\b", "filter: blur"),
    ]
    found = []
    for pattern, label in forbidden:
        if re.search(pattern, content, re.IGNORECASE):
            found.append(label)

    if found:
        return False, f"包含禁用效果：{', '.join(found)}"
    return True, ""


def check_file_size(path: str) -> tuple:
    """检查 6：文件大小不超过 200KB。"""
    size = os.path.getsize(path)
    size_kb = size / 1024
    if size > MAX_FILE_SIZE_BYTES:
        return False, f"文件大小 {size_kb:.1f}KB，超过 200KB 限制"
    return True, f"{size_kb:.1f}KB"


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────

def run_checks(html_path: str) -> int:
    if not os.path.exists(html_path):
        print(f"[ERROR] 文件不存在：{html_path}")
        return 1

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    allowed_colors = load_allowed_colors_from_tokens(STYLE_TOKENS_PATH)

    checks = [
        ("HTML 能解析",     check_html_parseable(content)),
        ("有动画逻辑",       check_animation_logic(content)),
        ("有循环机制",       check_loop_mechanism(content)),
        ("颜色合规",         check_colors(content, allowed_colors)),
        ("无禁用效果",       check_no_forbidden_effects(content)),
        ("文件大小合理",     check_file_size(html_path)),
    ]

    all_passed = True
    results = []

    for name, (result, detail) in checks:
        if result is True:
            status = "PASS"
            msg = f"  {detail}" if detail else ""
        elif result == "WARN":
            status = "WARN"
            msg = f"  {detail}"
        else:
            status = "FAIL"
            msg = f"  {detail}"
            all_passed = False
        results.append((status, name, msg))

    # 打印结果
    print(f"\n验证文件：{html_path}")
    print("─" * 50)
    for status, name, msg in results:
        icon = {"PASS": "✓", "WARN": "?", "FAIL": "✗"}[status]
        print(f"[{status}] {icon} {name}{msg}")
    print("─" * 50)

    if all_passed:
        has_warn = any(s == "WARN" for s, _, _ in results)
        if has_warn:
            print("结论：通过（有警告，建议人工复查）\n")
        else:
            print("结论：全部通过\n")
        return 0
    else:
        fail_count = sum(1 for s, _, _ in results if s == "FAIL")
        print(f"结论：未通过（{fail_count} 项不合格）\n")
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 harness/validate.py <html文件路径>")
        sys.exit(1)

    sys.exit(run_checks(sys.argv[1]))
