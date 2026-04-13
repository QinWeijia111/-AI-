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

    for chapter_name in chapters:
        print(f"\n{'='*60}")
        print(f"解题 {chapter_name}")
        print(f"{'='*60}")

        results = solve_all_chapter(client, model, chapter_name, parsed_dir, solutions_dir)
        print(f"\n  {chapter_name} 完成: {len(results)} 道题目已解答")

    # 生成汇总文件
    print(f"\n{'='*60}")
    print("生成汇总文件...")
    solutions_dir.mkdir(parents=True, exist_ok=True)
    all_path = generate_all_solutions_md(solutions_dir)
    print(f"汇总文件: {all_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
