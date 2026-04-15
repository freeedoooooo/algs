from __future__ import annotations

import re
import shutil
from pathlib import Path

from nbconvert import MarkdownExporter


ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT / ".site-docs"

MARKDOWN_ROOT_FILES = [
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

JAVA_SOURCE_DIRS = [
    "solutions-java",
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


def build_homepage() -> None:
    content = """# algs

个人算法学习站点，主要整理三类内容：

- LeetCode 高频题解与 Notebook
- Java 解法迁移到 Python 的对照整理
- 系统化算法笔记与字符串专题

## 这个站里有什么

### Python 题解整理

- [Top100 路线总表](solutions-python/top100.md)
- [Top100 Notebook 列表](solutions-python/top100/index.md)
- [Java 转 Python 总表](solutions-python/java2python.md)
- [Java 转 Python Notebook 列表](solutions-python/java2python/index.md)

### 算法笔记

- [算法笔记总览](my-notes/README.md)
- [基础巩固](my-notes/01-基础巩固/README.md)
- [基础提升](my-notes/02-基础提升/README.md)
- [中级提升](my-notes/03-中级提升/README.md)
- [大厂真题](my-notes/09-大厂真题/README.md)

### 专题整理

- [字符串专题入口](string-algs/index.md)
- [LeetCode 讲解模板](solutions-python/leetcode_explanation_template.md)
- [刷题策略](solutions-python/leetcode_practice_strategy.md)

## 推荐阅读路径

如果你是第一次来到这里，推荐按下面顺序看：

1. 先看 [刷题策略](solutions-python/leetcode_practice_strategy.md)，建立整体节奏
2. 再从 [Top100 路线总表](solutions-python/top100.md) 进入高频题
3. 需要看源码迁移时，进入 [Java 转 Python 总表](solutions-python/java2python.md)
4. 想系统补基础，就从 [算法笔记总览](my-notes/README.md) 开始

## 当前内容特点

- 更偏中文面试语境，强调题型、优先级、学习顺序
- 不只放代码，也会补充题意理解、图解、应用场景和面试表达
- Notebook 题解与系统笔记并行整理，适合“刷题 + 建知识体系”一起推进

## 快速开始

- 想直接开始刷题：进入 [Top100 路线](solutions-python/top100.md)
- 想看已经整理好的 Notebook：进入 [Top100 Notebook 列表](solutions-python/top100/index.md)
- 想看链表/树/递归等系统笔记：进入 [算法笔记](my-notes/README.md)
- 想了解仓库结构本身：进入 [仓库说明](repo-readme.md)
"""
    write_markdown(DOCS_DIR / "index.md", content)


def build_repo_readme_page() -> None:
    src = ROOT / "README.md"
    content = src.read_text(encoding="utf-8")
    write_markdown(DOCS_DIR / "repo-readme.md", content)


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
        if src.suffix.lower() == ".md":
            content = src.read_text(encoding="utf-8")
            content = rewrite_markdown_links(content)
            dest.write_text(content, encoding="utf-8")
            continue
        shutil.copy2(src, dest)


def rewrite_markdown_links(content: str) -> str:
    pattern = re.compile(r"(\[[^\]]+\]\(([^)#]+?\.java)(#[^)]+)?\))")

    def replace(match: re.Match[str]) -> str:
        full_match = match.group(1)
        java_path = match.group(2)
        anchor = match.group(3) or ""
        return full_match.replace(f"{java_path}{anchor}", f"{java_path}.md{anchor}")

    return pattern.sub(replace, content)


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


def convert_java_file(src: Path, dest_md: Path) -> None:
    source = src.read_text(encoding="utf-8")
    title = src.stem
    content = "\n".join(
        [
            f"# {title}",
            "",
            f"源码路径：`{src.relative_to(ROOT).as_posix()}`",
            "",
            "```java",
            source.rstrip(),
            "```",
        ]
    )
    write_markdown(dest_md, content)


def convert_java_tree(relative_dir: str) -> None:
    src_root = ROOT / relative_dir
    dest_root = DOCS_DIR / relative_dir
    for src in src_root.rglob("*.java"):
        rel_path = src.relative_to(src_root)
        dest_md = (dest_root / rel_path).with_suffix(src.suffix + ".md")
        convert_java_file(src, dest_md)


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


def build_solutions_java_index() -> None:
    content = """# solutions-java

这里整理当前仓库里的 Java 历史实现源码页，主要用于：

- 给算法笔记中的源码引用提供可点击入口
- 保留 Java 版本实现，方便与 Python 题解对照阅读

当前内容以源码浏览为主。
"""
    write_markdown(DOCS_DIR / "solutions-java" / "index.md", content)


def main() -> None:
    reset_docs_dir()
    copy_root_files()
    build_homepage()
    build_repo_readme_page()
    for relative_dir in CONTENT_DIRS:
        copy_content_tree(relative_dir)
    for relative_dir in NOTEBOOK_DIRS:
        convert_notebook_tree(relative_dir)
    for relative_dir in JAVA_SOURCE_DIRS:
        convert_java_tree(relative_dir)

    build_solutions_python_index()
    build_solutions_java_index()
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
