"""Step 1: Qwen 多模态识别引擎。

将题目图片（题干+题图）通过 Qwen 视觉模型识别，
转录为 Markdown 格式（含 LaTeX 公式和 Mermaid 图）。
"""

import os
from pathlib import Path
from openai import OpenAI

from ct_solver.scanner import Problem, scan_problems
from ct_solver.prompts import STEP1_SYSTEM_PROMPT


def create_client() -> OpenAI:
    """从环境变量创建 Qwen API 客户端。"""
    base_url = os.environ.get("QWEN_BASE_URL", "http://127.0.0.1:8317")
    api_key = os.environ.get("QWEN_API_KEY", "sk-JHpV94x2aQrYgA6OX")
    return OpenAI(base_url=base_url, api_key=api_key)


def encode_image(image_path: str) -> str:
    """将本地图片编码为 base64 data URL。"""
    import base64
    from pathlib import Path

    path = Path(image_path)
    suffix = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }
    mime = mime_map.get(suffix, "image/jpeg")

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime};base64,{encoded}"


def parse_problem(client: OpenAI, model: str, problem: Problem) -> str:
    """调用 Qwen 视觉模型识别一道题目。

    Returns:
        识别出的 Markdown 文本
    """
    # 构建消息内容
    content = []

    # 添加所有题干图片
    for img_path in problem.question_images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": encode_image(img_path),
                "detail": "high"
            }
        })

    # 添加所有题图
    for img_path in problem.diagram_images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": encode_image(img_path),
                "detail": "high"
            }
        })

    # 添加文字提示
    image_info = ""
    if problem.has_diagram:
        image_info = f"\n（本题包含 {len(problem.diagram_images)} 张题干图和 {len(problem.diagram_images)} 张题图，请全部识别）"
    else:
        image_info = f"\n（本题包含 {len(problem.question_images)} 张题干图，请识别）"

    content.append({
        "type": "text",
        "text": f"题目编号: {problem.problem_id}{image_info}\n\n请按系统提示词的要求进行识别和转录。"
    })

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": STEP1_SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ],
        temperature=0.1,
        max_tokens=4096,
    )

    return response.choices[0].message.content


def save_parsed(problem: Problem, content: str, output_dir: Path) -> Path:
    """保存解析结果到 output/parsed/第X章/X.Y.md。"""
    chapter_dir = output_dir / problem.chapter
    chapter_dir.mkdir(parents=True, exist_ok=True)

    output_path = chapter_dir / f"{problem.problem_id}.md"
    output_path.write_text(content, encoding="utf-8")
    return output_path


def parse_all_chapter(client: OpenAI, model: str, chapter_name: str,
                      image_dir: Path, output_dir: Path) -> list[tuple[str, str]]:
    """解析指定章节的所有题目。

    Returns:
        [(problem_id, output_path_str), ...]
    """
    all_problems = scan_problems(image_dir)
    chapter_problems = [p for p in all_problems if p.chapter == chapter_name]

    if not chapter_problems:
        print(f"  未在 {chapter_name} 中找到题目")
        return []

    results = []
    for i, problem in enumerate(chapter_problems):
        parsed_file = output_dir / "parsed" / problem.chapter / f"{problem.problem_id}.md"

        # 断点续传：跳过已解析的题目
        if parsed_file.exists():
            print(f"  [{i+1}/{len(chapter_problems)}] 跳过 {problem.problem_id} (已存在)")
            results.append((problem.problem_id, str(parsed_file)))
            continue

        print(f"  [{i+1}/{len(chapter_problems)}] 识别 {problem.problem_id}...")
        try:
            content = parse_problem(client, model, problem)
            out_path = save_parsed(problem, content, output_dir)
            results.append((problem.problem_id, str(out_path)))
            print(f"    -> 已保存到 {out_path}")
        except Exception as e:
            print(f"    -> 错误: {e}")

    return results


def generate_all_problems_md(output_dir: Path) -> Path:
    """将所有解析结果汇总到 all_problems.md。"""
    parsed_dir = output_dir / "parsed"
    all_problems_path = output_dir / "all_problems.md"

    lines = ["# 计算理论课后题 — 全部题目解析\n"]

    # 按章节排序
    chapter_dirs = sorted(
        [d for d in parsed_dir.iterdir() if d.is_dir()],
        key=lambda d: _chapter_sort_key(d.name)
    )

    for chapter_dir in chapter_dirs:
        chapter_name = chapter_dir.name
        lines.append(f"\n## {chapter_name}\n")

        # 按题号排序
        problem_files = sorted(
            [f for f in chapter_dir.iterdir() if f.suffix == ".md"],
            key=lambda f: _problem_sort_key(f.stem)
        )

        for pf in problem_files:
            content = pf.read_text(encoding="utf-8")
            lines.append(content)
            lines.append("")

    all_problems_path.write_text("\n".join(lines), encoding="utf-8")
    return all_problems_path


def _chapter_sort_key(name: str) -> int:
    try:
        return int(name.replace("第", "").replace("章", ""))
    except ValueError:
        return 999


def _problem_sort_key(name: str) -> float:
    try:
        return float(name)
    except ValueError:
        return 999.0
