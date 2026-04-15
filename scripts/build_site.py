from __future__ import annotations

import shutil
from pathlib import Path

from nbconvert import MarkdownExporter


ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / ".site-docs"

MARKDOWN_ROOT_FILES = [
    "README.md",
    "SITE_DEPLOYMENT.md",
]

CONTENT_DIRS = [
    "my-notes",
    "solutions-python",
    "string-algs",
]

NOTEBOOK_DIRS = [
    "solutions-python/top100",
    "solutions-python/java2python",
]


def reset_docs_dir() -> None:
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def copy_root_files() -> None:
    for file_name in MARKDOWN_ROOT_FILES:
        src = ROOT / file_name
        dest_name = "index.md" if file_name == "README.md" else file_name
        shutil.copy2(src, DOCS_DIR / dest_name)


def copy_content_tree(relative_dir: str) -> None:
    src_root = ROOT / relative_dir
    dest_root = DOCS_DIR / relative_dir
    for src in src_root.rglob("*"):
        if src.is_dir():
            continue
        rel_path = src.relative_to(src_root)
        dest = dest_root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".ipynb":
            continue
        shutil.copy2(src, dest)


def convert_notebook(src: Path, dest_md: Path) -> None:
    exporter = MarkdownExporter()
    resources = {
        "output_files_dir": f"{src.stem}_files",
        "unique_key": src.stem,
    }
    body, converted = exporter.from_filename(str(src), resources=resources)

    dest_md.parent.mkdir(parents=True, exist_ok=True)
    raw_notebook_dest = dest_md.with_suffix(".ipynb")
    shutil.copy2(src, raw_notebook_dest)

    output_files_dir = dest_md.parent / converted["output_files_dir"]
    for file_name, data in converted.get("outputs", {}).items():
        target = output_files_dir / file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    download_note = (
        f"> 原始 Notebook 下载："
        f"[{raw_notebook_dest.name}]({raw_notebook_dest.name})\n\n"
    )
    dest_md.write_text(download_note + body, encoding="utf-8")


def convert_notebook_tree(relative_dir: str) -> None:
    src_root = ROOT / relative_dir
    dest_root = DOCS_DIR / relative_dir
    for src in src_root.rglob("*.ipynb"):
        rel_path = src.relative_to(src_root)
        dest_md = (dest_root / rel_path).with_suffix(".md")
        convert_notebook(src, dest_md)


def notebook_title_from_name(stem: str) -> str:
    if "_" not in stem:
        return stem
    problem_id, slug = stem.split("_", 1)
    words = slug.split("_")
    return f"{problem_id} {' '.join(word.capitalize() for word in words)}"


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_notebook_index(relative_dir: str, title: str, description: str) -> None:
    dir_path = DOCS_DIR / relative_dir
    notebook_files = sorted(dir_path.glob("*.md"))
    lines = [
        f"# {title}",
        "",
        description,
        "",
    ]
    for notebook in notebook_files:
        if notebook.name == "index.md":
            continue
        label = notebook_title_from_name(notebook.stem)
        raw_name = notebook.with_suffix(".ipynb").name
        lines.append(f"- [{label}]({notebook.name}) | [下载 ipynb]({raw_name})")
    write_markdown(dir_path / "index.md", "\n".join(lines))


def build_solutions_python_index() -> None:
    content = """# solutions-python

这里汇总当前仓库中的 Python 题解整理内容，主要分为两条线：

- `Top100`：按国内算法面试高频题顺序整理
- `Java2Python`：基于已有 Java 解法迁移整理为 Python Notebook

可直接进入以下入口：

- [Top100 总表](top100.md)
- [Java 转 Python 总表](java2python.md)
- [LeetCode 讲解模板](leetcode_explanation_template.md)
- [刷题策略](leetcode_practice_strategy.md)
- [Top100 Notebook 列表](top100/index.md)
- [Java 转 Python Notebook 列表](java2python/index.md)
"""
    write_markdown(DOCS_DIR / "solutions-python" / "index.md", content)


def build_string_algs_index() -> None:
    content = """# string-algs

字符串相关专题整理入口：

- [字符串算法补充](string_algs_appendix.md)
"""
    write_markdown(DOCS_DIR / "string-algs" / "index.md", content)


def main() -> None:
    reset_docs_dir()
    copy_root_files()
    for relative_dir in CONTENT_DIRS:
        copy_content_tree(relative_dir)
    for relative_dir in NOTEBOOK_DIRS:
        convert_notebook_tree(relative_dir)

    build_solutions_python_index()
    build_string_algs_index()
    build_notebook_index(
        "solutions-python/top100",
        "Top100 Notebook 列表",
        "这里收录当前 Top100 路线下已经整理完成的 Jupyter Notebook 解析。",
    )
    build_notebook_index(
        "solutions-python/java2python",
        "Java 转 Python Notebook 列表",
        "这里收录基于原有 Java 解法迁移整理得到的 Python Notebook。",
    )


if __name__ == "__main__":
    main()
