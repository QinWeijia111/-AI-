#!/usr/bin/env python3
"""Step 2 入口：DeepSeek 解答题目。

用法:
    uv run python scripts/run_step2.py                  # 全量运行所有章节
    uv run python scripts/run_step2.py --chapter 0      # 仅运行第0章
    uv run python scripts/run_step2.py --chapter 1,2    # 运行第1章和第2章
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description="Step 2: DeepSeek 解答题目")
    parser.add_argument("--chapter", type=str, default=None,
                        help="指定章节，如 0 或 0,1,2（省略则全量运行）")
    args = parser.parse_args()

    # 加载 .env
    load_dotenv()

    output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
    solutions_dir = Path(os.environ.get("SOLUTIONS_DIR", "solutions"))
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    timeout_seconds = int(os.environ.get("STEP_TIMEOUT_SECONDS", "300"))

    # 导入模块
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from ct_solver.step2_solve import (
        create_client, solve_all_chapter, generate_all_solutions_md
    )

    parsed_dir = output_dir / "parsed"

    # 确定要处理的章节
    if parsed_dir.exists():
        all_chapters = sorted(
            [d.name for d in parsed_dir.iterdir() if d.is_dir()],
            key=lambda c: int(c.replace("第", "").replace("章", ""))
        )
    else:
        print("错误: 未找到解析结果目录，请先运行 Step 1")
        print(f"  预期路径: {parsed_dir}")
        sys.exit(1)

    if args.chapter:
        chapters = [f"第{c.strip()}章" for c in args.chapter.split(",")]
        # 验证章节存在
        for ch in chapters:
            if ch not in all_chapters:
                print(f"警告: {ch} 不存在于解析结果中，跳过")
        chapters = [ch for ch in chapters if ch in all_chapters]
    else:
        chapters = all_chapters

    if not chapters:
        print("没有需要处理的章节")
        sys.exit(1)

    client = create_client()
    all_unfinished: list[dict[str, str]] = []

    for chapter_name in chapters:
        print(f"\n{'='*60}")
        print(f"解题 {chapter_name}（单题超时 {timeout_seconds} 秒）")
        print(f"{'='*60}")

        summary = solve_all_chapter(client, model, chapter_name, parsed_dir, solutions_dir)
        completed_count = len(summary["completed"])
        unfinished = summary["unfinished"]
        all_unfinished.extend(
            [{"chapter": chapter_name, **item} for item in unfinished]
        )

        print(f"\n  {chapter_name} 完成: {completed_count} 道题目已解答")
        if unfinished:
            print("  未完成题目:")
            for item in unfinished:
                print(f"    - {item['problem_id']}: {item['reason']}")

    # 生成汇总文件
    print(f"\n{'='*60}")
    print("生成汇总文件...")
    solutions_dir.mkdir(parents=True, exist_ok=True)
    all_path = generate_all_solutions_md(solutions_dir)
    print(f"汇总文件: {all_path}")
    unfinished_path = solutions_dir / "unfinished_step2.md"
    if all_unfinished:
        unfinished_lines = ["# Step 2 未完成题目\n"]
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
