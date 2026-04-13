#!/usr/bin/env python3
"""重建汇总文件，不重新调用模型。"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv()

    output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
    solutions_dir = Path(os.environ.get("SOLUTIONS_DIR", "solutions"))

    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from ct_solver.step1_parse import generate_all_problems_md
    from ct_solver.step2_solve import generate_all_solutions_md

    print("重建 Step 1 汇总文件...")
    output_dir.mkdir(parents=True, exist_ok=True)
    problems_path = generate_all_problems_md(output_dir)
    print(f"  -> {problems_path}")

    print("重建 Step 2 汇总文件...")
    solutions_dir.mkdir(parents=True, exist_ok=True)
    solutions_path = generate_all_solutions_md(solutions_dir)
    print(f"  -> {solutions_path}")


if __name__ == "__main__":
    main()
