"""题目扫描器：遍历计算理论课后题目录，返回结构化题目列表。"""

import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class Problem:
    """一道题目的结构化信息。"""
    chapter: str          # 章节名，如 "第0章"
    problem_id: str       # 题号，如 "0.10"
    question_images: list[str]  # 题干图片路径列表
    diagram_images: list[str]   # 题图图片路径列表（可能为空）

    @property
    def has_diagram(self) -> bool:
        return len(self.diagram_images) > 0


def scan_problems(image_dir: str | Path) -> list[Problem]:
    """扫描题目目录结构，返回所有题目的列表。

    目录结构约定:
        计算理论课后题/
            第0章/
                0.10/
                    题干.png
                    题图.png (可选)
                0.11/
                    题干.jpg
    """
    image_dir = Path(image_dir)
    if not image_dir.exists():
        raise FileNotFoundError(f"题目图片目录不存在: {image_dir}")

    problems: list[Problem] = []

    # 按章节名排序（第0章, 第1章, ...）
    chapter_dirs = sorted(
        [d for d in image_dir.iterdir() if d.is_dir()],
        key=lambda d: _chapter_sort_key(d.name)
    )

    for chapter_dir in chapter_dirs:
        chapter_name = chapter_dir.name

        # 按题号排序
        problem_dirs = sorted(
            [d for d in chapter_dir.iterdir() if d.is_dir()],
            key=lambda d: _problem_sort_key(d.name)
        )

        for problem_dir in problem_dirs:
            problem_id = problem_dir.name
            question_images = []
            diagram_images = []

            for f in problem_dir.iterdir():
                if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png"):
                    if f.name.startswith("题干"):
                        question_images.append(str(f))
                    elif f.name.startswith("题图"):
                        diagram_images.append(str(f))

            question_images.sort()
            diagram_images.sort()

            if question_images:  # 只添加有题干的题目
                problems.append(Problem(
                    chapter=chapter_name,
                    problem_id=problem_id,
                    question_images=question_images,
                    diagram_images=diagram_images,
                ))

    return problems


def _chapter_sort_key(name: str) -> int:
    """从 '第X章' 提取 X 用于排序。"""
    try:
        return int(name.replace("第", "").replace("章", ""))
    except ValueError:
        return 999


def _problem_sort_key(name: str) -> float:
    """从 'X.Y' 提取浮点数用于排序。"""
    try:
        return float(name)
    except ValueError:
        return 999.0
