"""Step 2: DeepSeek 解题引擎。

读取 Step 1 的解析结果，调用 DeepSeek chat 模型解题，
整理为包含"原题题干 + Mermaid + 解题结果"的格式。
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from openai import APITimeoutError, OpenAI

from ct_solver.scanner import scan_problems
from ct_solver.prompts import STEP2_SYSTEM_PROMPT


def create_client() -> OpenAI:
    """从环境变量创建 DeepSeek API 客户端。"""
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise ValueError("请设置环境变量 DEEPSEEK_API_KEY")
    timeout_seconds = int(os.environ.get("STEP_TIMEOUT_SECONDS", "300"))
    return OpenAI(base_url=base_url, api_key=api_key, timeout=timeout_seconds)


def normalize_latex_markdown(text: str) -> str:
    r"""将 \(...\) / \[...\] 转为 Markdown 兼容的 $...$ / $$...$$。"""
    text = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", text, flags=re.DOTALL)
    text = re.sub(r"\\\((.*?)\\\)", r"$\1$", text, flags=re.DOTALL)
    return text


def solve_problem(client: OpenAI, model: str, chapter: str,
                  problem_id: str, question_text: str,
                  mermaid_code: str | None = None) -> str:
    """调用 DeepSeek 解题。

    Returns:
        解题结果的 Markdown 文本
    """
    # 构建题干和题图部分
    diagram_section = ""
    if mermaid_code:
        diagram_section = f"\n## 题图（Mermaid 状态图/流程图）\n```mermaid\n{mermaid_code}\n```"

    user_prompt = f"""## 题干
{question_text}
{diagram_section}

请按照系统提示词的要求进行解题。"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": STEP2_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.1,
        max_tokens=8192,
    )

    return normalize_latex_markdown(response.choices[0].message.content)


def parse_parsed_md(file_path: Path) -> tuple[str, str | None]:
    """解析 Step 1 生成的 md 文件，提取题干和题图 Mermaid。

    Returns:
        (question_text, mermaid_code | None)
    """
    content = file_path.read_text(encoding="utf-8")

    question_text = ""
    mermaid_code = None

    # 分割 ### 题干 和 ### 题图 Mermaid
    if "### 题图 Mermaid" in content:
        parts = content.split("### 题图 Mermaid")
        question_text = parts[0].replace("### 题干", "").strip()

        mermaid_part = parts[1]
        # 提取 ```mermaid ... ``` 中的内容
        if "```mermaid" in mermaid_part:
            start = mermaid_part.index("```mermaid") + len("```mermaid")
            end = mermaid_part.index("```", start)
            mermaid_code = mermaid_part[start:end].strip()
    else:
        # 没有题图，整个内容都是题干
        question_text = content.replace("### 题干", "").strip()

    return question_text, mermaid_code


def save_solution(chapter: str, problem_id: str,
                  question_text: str, mermaid_code: str | None,
                  solution_text: str, solutions_dir: Path) -> Path:
    """保存解题结果。

    格式:
        # 题目 X.Y

        ## 原题题干
        [Step 1 解析出的题干文字]

        ## 题图 Mermaid
        [Step 1 解析出的 Mermaid 代码]

        ## 解题结果
        [DeepSeek 返回的答案]
    """
    chapter_dir = solutions_dir / "per_problem" / chapter
    chapter_dir.mkdir(parents=True, exist_ok=True)

    output_path = chapter_dir / f"{problem_id}.md"

    lines = [f"# 题目 {problem_id}\n"]
    lines.append(f"\n## 原题题干\n{question_text}\n")

    if mermaid_code:
        lines.append(f"\n## 题图 Mermaid\n```mermaid\n{mermaid_code}\n```\n")

    lines.append(f"\n## 解题结果\n{solution_text}\n")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _solve_one_problem(client: OpenAI, model: str, chapter_name: str,
                       problem_file: Path, solutions_dir: Path) -> dict[str, str]:
    """并发 worker：解一道题并返回结果摘要。"""
    problem_id = problem_file.stem
    solution_file = solutions_dir / "per_problem" / chapter_name / f"{problem_id}.md"

    if solution_file.exists():
        return {"status": "completed", "problem_id": problem_id, "path": str(solution_file)}

    question_text, mermaid_code = parse_parsed_md(problem_file)
    solution_text = solve_problem(
        client, model, chapter_name, problem_id,
        question_text, mermaid_code
    )
    out_path = save_solution(
        chapter_name, problem_id,
        question_text, mermaid_code,
        solution_text, solutions_dir
    )
    return {"status": "completed", "problem_id": problem_id, "path": str(out_path)}


def solve_all_chapter(client: OpenAI, model: str, chapter_name: str,
                      parsed_dir: Path, solutions_dir: Path) -> dict[str, list[dict[str, str]]]:
    """解题指定章节的所有题目。

    Returns:
        {
            "completed": [{"problem_id": ..., "path": ...}],
            "unfinished": [{"problem_id": ..., "reason": ...}],
        }
    """
    chapter_parsed_dir = parsed_dir / chapter_name
    if not chapter_parsed_dir.exists():
        print(f"  解析目录不存在: {chapter_parsed_dir}")
        return {"completed": [], "unfinished": []}

    problem_files = sorted(
        [f for f in chapter_parsed_dir.iterdir() if f.suffix == ".md"],
        key=lambda f: _problem_sort_key(f.stem)
    )

    if not problem_files:
        print(f"  未在 {chapter_name} 中找到解析文件")
        return {"completed": [], "unfinished": []}

    completed = []
    unfinished = []
    concurrency = max(1, int(os.environ.get("STEP2_CONCURRENCY", "6")))

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_problem = {
            executor.submit(_solve_one_problem, client, model, chapter_name, pf, solutions_dir): pf
            for pf in problem_files
        }

        for future in as_completed(future_to_problem):
            pf = future_to_problem[future]
            problem_id = pf.stem
            try:
                result = future.result()
                completed.append({
                    "problem_id": result["problem_id"],
                    "path": result["path"],
                })
                print(f"  完成 {problem_id} -> {result['path']}")
            except APITimeoutError:
                reason = "超时（超过 5 分钟）"
                unfinished.append({"problem_id": problem_id, "reason": reason})
                print(f"  未完成 {problem_id}: {reason}")
            except Exception as e:
                reason = f"错误: {e}"
                unfinished.append({"problem_id": problem_id, "reason": reason})
                print(f"  未完成 {problem_id}: {reason}")

    completed.sort(key=lambda item: _problem_sort_key(item["problem_id"]))
    unfinished.sort(key=lambda item: _problem_sort_key(item["problem_id"]))
    return {"completed": completed, "unfinished": unfinished}


def generate_all_solutions_md(solutions_dir: Path) -> Path:
    """将所有解题结果汇总到 all_solutions.md。"""
    per_problem_dir = solutions_dir / "per_problem"
    all_solutions_path = solutions_dir / "all_solutions.md"

    lines = ["# 计算理论课后题 — 全部解题结果\n"]

    if not per_problem_dir.exists():
        all_solutions_path.write_text("\n".join(lines), encoding="utf-8")
        return all_solutions_path

    # 按章节排序
    chapter_dirs = sorted(
        [d for d in per_problem_dir.iterdir() if d.is_dir()],
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

    all_solutions_path.write_text("\n".join(lines), encoding="utf-8")
    return all_solutions_path


def _chapter_sort_key(name: str) -> int:
    try:
        return int(name.replace("第", "").replace("章", ""))
    except ValueError:
        return 999


def _problem_sort_key(name: str) -> tuple[int, int]:
    try:
        chapter_str, problem_str = name.split(".", 1)
        return int(chapter_str), int(problem_str)
    except ValueError:
        return 999, 999
