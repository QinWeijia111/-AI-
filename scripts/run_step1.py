#!/usr/bin/env python3
"""Step 1 入口：Qwen 多模态识别题目图片。

用法:
    uv run python scripts/run_step1.py                  # 全量运行所有章节
    uv run python scripts/run_step1.py --chapter 0      # 仅运行第0章
    uv run python scripts/run_step1.py --chapter 1,2    # 运行第1章和第2章
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description="Step 1: Qwen 多模态识别题目图片")
    parser.add_argument("--chapter", type=str, default=None,
                        help="指定章节，如 0 或 0,1,2（省略则全量运行）")
    args = parser.parse_args()

    # 加载 .env
    load_dotenv()

    image_dir = Path(os.environ.get("PROBLEM_IMAGE_DIR", "计算理论课后题"))
    output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
    model = os.environ.get("QWEN_MODEL", "coder-model")
    timeout_seconds = int(os.environ.get("STEP_TIMEOUT_SECONDS", "300"))

    # 导入模块（需要 PYTHONPATH 指向 src/）
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from ct_solver.step1_parse import (
        create_client, parse_all_chapter, generate_all_problems_md
    )
    from ct_solver.scanner import scan_problems

    # 扫描所有题目
    print(f"扫描题目目录: {image_dir}")
    all_problems = scan_problems(image_dir)
    print(f"共发现 {len(all_problems)} 道题目\n")

    # 确定要处理的章节
    if args.chapter:
        chapters = [f"第{c.strip()}章" for c in args.chapter.split(",")]
    else:
        chapters = sorted(
            set(p.chapter for p in all_problems),
            key=lambda c: int(c.replace("第", "").replace("章", ""))
        )

    client = create_client()
    all_unfinished: list[dict[str, str]] = []

    for chapter_name in chapters:
        print(f"\n{'='*60}")
        print(f"处理 {chapter_name}（单题超时 {timeout_seconds} 秒）")
        print(f"{'='*60}")

        summary = parse_all_chapter(client, model, chapter_name, image_dir, output_dir)
        completed_count = len(summary["completed"])
        unfinished = summary["unfinished"]
        all_unfinished.extend(
            [{"chapter": chapter_name, **item} for item in unfinished]
        )

        print(f"\n  {chapter_name} 完成: {completed_count} 道题目已解析")
        if unfinished:
            print("  未完成题目:")
            for item in unfinished:
                print(f"    - {item['problem_id']}: {item['reason']}")

    # 生成汇总文件
    print(f"\n{'='*60}")
    print("生成汇总文件...")
    output_dir.mkdir(parents=True, exist_ok=True)
    all_path = generate_all_problems_md(output_dir)
    print(f"汇总文件: {all_path}")
    unfinished_path = output_dir / "unfinished_step1.md"
    if all_unfinished:
        unfinished_lines = ["# Step 1 未完成题目\n"]
        for item in all_unfinished:
            unfinished_lines.append(
                f"- {item['chapter']}/{item['problem_id']}: {item['reason']}"
            )
        unfinished_path.write_text("\n".join(unfinished_lines), encoding="utf-8")
        print("未完成题目汇总:")
        for item in all_unfinished:
            print(f"  - {item['chapter']}/{item['problem_id']}: {item['reason']}")
        print(f"未完成清单: {unfinished_path}")
    elif unfinished_path.exists():
        unfinished_path.unlink()
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
