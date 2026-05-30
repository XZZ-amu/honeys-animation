#!/usr/bin/env python3
"""快速生成创作日志的交互式脚本"""

import os
from datetime import date


def prompt(question: str) -> str:
    """单行输入"""
    return input(f"{question} ").strip()


def prompt_multiline(question: str) -> list[str]:
    """多行输入，空行结束"""
    print(f"{question}（空行结束）")
    lines = []
    while True:
        line = input("  > ").strip()
        if line == "":
            break
        lines.append(line)
    return lines


def main():
    print("\n=== 创作日志生成器 ===\n")

    # 1. 动画文件名
    animation_file = prompt("1. 动画文件名？（如 20-sand-erosion-v2.html）")

    # 2. 用户原始输入
    user_input = prompt("2. 用户原始输入是什么？（一句话）")

    # 3. 迭代轮次
    iterations = prompt("3. 迭代了几轮？")

    # 4. 最终满意度
    satisfaction_raw = prompt("4. 最终满意吗？（满意/部分满意/不满意）")

    # 5. 做对了什么
    success_points = prompt_multiline("5. 做对了什么？")

    # 6. 做错了什么
    failure_points = prompt_multiline("6. 做错了什么？")

    # 7. 新规则
    has_new_rule = prompt("7. 有新规则要加吗？（有/没有）")
    new_rules = []
    if has_new_rule.strip() in ("有", "y", "yes", "Y"):
        new_rules = prompt_multiline("   规则名是什么？")

    # 生成文件名
    today = date.today().strftime("%Y-%m-%d")
    # 去掉后缀，取文件名部分
    base_name = os.path.splitext(os.path.basename(animation_file))[0]
    output_filename = f"{today}-{base_name}.md"

    # 拼装 Markdown 内容
    success_md = "\n".join(f"- {p}" for p in success_points) if success_points else "- （无）"
    failure_md = "\n".join(f"- {p}" for p in failure_points) if failure_points else "- （无）"

    if new_rules:
        rules_md = "- 是：" + "、".join(new_rules)
    else:
        rules_md = "- 否"

    content = f"""# 创作记录：{base_name}

## 基本信息
- 动画文件：{animation_file}
- 用户原始输入："{user_input}"
- 迭代轮次：{iterations} 轮
- 最终状态：{satisfaction_raw}

## 迭代历史
- （请补充各版本的变化和问题）

## 成功点
{success_md}

## 失败点
{failure_md}

## 是否产生新规则
{rules_md}

## 关键认知
- （请补充本次最重要的一条认知）
"""

    # 写文件
    logs_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    output_path = os.path.join(logs_dir, output_filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n日志已生成：{output_path}\n")


if __name__ == "__main__":
    main()
