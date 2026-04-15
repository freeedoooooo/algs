from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT / ".site-docs"
NOTES_DIR = "my-notes"
JAVA_SOURCE_DIR = "solutions-java"


def reset_docs_dir() -> None:
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def build_homepage() -> None:
    content = """# 我的算法笔记

这是一个以 `my-notes` 为核心整理的个人算法笔记站。

这里主要收录：

- 基础巩固阶段的系统笔记
- 基础提升与中级提升阶段的专题内容
- 大厂真题与补充题目

## 从哪里开始看

- [笔记总览](my-notes/README.md)
- [基础巩固](my-notes/01-基础巩固/README.md)
- [基础提升](my-notes/02-基础提升/README.md)
- [中级提升](my-notes/03-中级提升/README.md)
- [大厂真题](my-notes/09-大厂真题/README.md)

## 推荐阅读路径

1. 先从 [基础巩固](my-notes/01-基础巩固/README.md) 建立常见数据结构和递归/动态规划基础
2. 再进入 [基础提升](my-notes/02-基础提升/README.md) 学习 KMP、滑动窗口、并查集等专题
3. 接着看 [中级提升](my-notes/03-中级提升/README.md) 做更偏面试和综合应用的训练
4. 最后结合 [大厂真题](my-notes/09-大厂真题/README.md) 做面试场景练习

## 这个站点的特点

- 以中文算法学习路径为主
- 更强调知识体系，而不只是题目答案
- 保留部分 Java 源码引用，方便结合历史实现理解
"""
    write_markdown(DOCS_DIR / "index.md", content)


def rewrite_markdown_links(content: str) -> str:
    pattern = re.compile(r"(\[[^\]]+\]\(([^)#]+?\.java)(#[^)]+)?\))")

    def replace(match: re.Match[str]) -> str:
        full_match = match.group(1)
        java_path = match.group(2)
        anchor = match.group(3) or ""
        return full_match.replace(f"{java_path}{anchor}", f"{java_path}.md{anchor}")

    return pattern.sub(replace, content)


def copy_notes_tree() -> None:
    src_root = ROOT / NOTES_DIR
    dest_root = DOCS_DIR / NOTES_DIR
    for src in src_root.rglob("*"):
        if src.is_dir():
            continue
        rel_path = src.relative_to(src_root)
        dest = dest_root / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix.lower() == ".md":
            content = src.read_text(encoding="utf-8")
            dest.write_text(rewrite_markdown_links(content), encoding="utf-8")
        else:
            shutil.copy2(src, dest)


def convert_java_file(src: Path, dest_md: Path) -> None:
    source = src.read_text(encoding="utf-8")
    content = "\n".join(
        [
            f"# {src.stem}",
            "",
            f"源码路径：`{src.relative_to(ROOT).as_posix()}`",
            "",
            "```java",
            source.rstrip(),
            "```",
        ]
    )
    write_markdown(dest_md, content)


def convert_java_tree() -> None:
    src_root = ROOT / JAVA_SOURCE_DIR
    dest_root = DOCS_DIR / JAVA_SOURCE_DIR
    for src in src_root.rglob("*.java"):
        rel_path = src.relative_to(src_root)
        dest_md = (dest_root / rel_path).with_suffix(src.suffix + ".md")
        convert_java_file(src, dest_md)


def main() -> None:
    reset_docs_dir()
    build_homepage()
    copy_notes_tree()
    convert_java_tree()


if __name__ == "__main__":
    main()
