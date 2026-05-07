from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT / ".site-docs"
NOTES_DIR = "my-notes"
JAVA_SOURCE_DIR = "solutions-java"

IGNORED_NOTE_DIRS = {"assets"}


def reset_docs_dir() -> None:
    if DOCS_DIR.exists():
        shutil.rmtree(DOCS_DIR)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def first_heading(path: Path) -> str | None:
    if not path.exists() or path.suffix.lower() != ".md":
        return None
    match = re.search(r"^#\s+(.+)$", path.read_text(encoding="utf-8"), re.M)
    if match:
        return match.group(1).strip()
    return None


def pretty_name(name: str) -> str:
    if "-" in name:
        return name.split("-", 1)[1].strip()
    return name


def iter_note_section_dirs() -> list[Path]:
    notes_root = ROOT / NOTES_DIR
    return sorted(
        [
            p
            for p in notes_root.iterdir()
            if p.is_dir() and not p.name.startswith(".") and p.name not in IGNORED_NOTE_DIRS
        ],
        key=lambda p: p.name,
    )


def section_title(section_root: Path) -> str:
    return first_heading(section_root / "README.md") or pretty_name(section_root.name)


def section_chapter_dirs(section_root: Path) -> list[Path]:
    return sorted([p for p in section_root.iterdir() if p.is_dir()], key=lambda p: p.name)


def section_slug(section_root: Path) -> str:
    return f"{section_root.name}.md"


def build_generated_readme(src_dir: Path) -> str | None:
    title = first_heading(src_dir / "README.md") or pretty_name(src_dir.name)
    lines = [
        f"# {title}",
        "",
        "该目录原始仓库中没有 `README.md`，构建时自动生成一个总览页，方便站点内导航。",
        "",
        "## 目录",
        "",
    ]

    entries: list[tuple[str, str]] = []
    for child in sorted(src_dir.iterdir()):
        if child.name.lower() == "readme.md":
            continue
        if child.is_dir():
            label = first_heading(child / "README.md") or pretty_name(child.name)
            entries.append((label, f"{child.name}/README.md"))
        elif child.suffix.lower() == ".md":
            label = first_heading(child) or child.stem
            entries.append((label, child.name))

    if not entries:
        return None

    for label, target in entries:
        lines.append(f"- [{label}]({target})")

    return "\n".join(lines)


def ensure_generated_readmes() -> None:
    src_root = ROOT / NOTES_DIR
    dest_root = DOCS_DIR / NOTES_DIR
    for src in src_root.rglob("*"):
        if not src.is_dir():
            continue
        src_readme = src / "README.md"
        if src_readme.exists():
            continue
        generated = build_generated_readme(src)
        if generated is None:
            continue
        dest_readme = dest_root / src.relative_to(src_root) / "README.md"
        write_markdown(dest_readme, generated)


def build_homepage() -> None:
    section_cards = []
    quick_links = ["- [笔记总览](my-notes/README.md)"]
    for section_root in iter_note_section_dirs():
        chapters = section_chapter_dirs(section_root)
        title = section_title(section_root)
        section_cards.append(
            "\n".join(
                [
                    f"-   **{title}**",
                    "",
                    "    ---",
                    "",
                    f"    该目录包含 {len(chapters)} 个章节，点击进入目录页继续浏览。",
                    "",
                    f"    [进入这一部分](sections/{section_slug(section_root)})",
                    "",
                ]
            )
        )
        quick_links.append(
            f"- [{title} 总览](my-notes/{section_root.name}/README.md)"
        )

    content = """# 我的算法笔记

> 一个围绕 `my-notes` 持续整理的个人算法学习站点。

这里不是单纯堆题解的地方，而更像一份按学习路径整理出来的算法知识地图：

- 用中文语境梳理算法知识体系
- 保留从基础到进阶的阅读顺序
- 把系统笔记、专题方法和面试题感放在同一条成长线上

## 从这里开始

<div class="grid cards" markdown>
"""
    content += "\n".join(section_cards)
    content += """

</div>

## 推荐阅读顺序

1. 如果你刚开始补算法，建议先从最前面的基础目录开始。
2. 看完一轮基础内容，再进入后面的专题目录。
3. 接着用中级目录训练综合题感和表达方式。
4. 最后结合大厂真题去接近真实面试节奏。

## 这个站点更适合谁

- 想系统补算法，而不是只零散刷题的人
- 想把“题目”连成“知识体系”的人
- 更习惯中文笔记、中文导图、中文面试表达的人

## 快速入口

"""
    content += "\n".join(quick_links)
    write_markdown(DOCS_DIR / "index.md", content)


def build_notes_overview() -> None:
    lines = [
        "# 笔记总览",
        "",
        "这里按当前仓库真实目录自动生成，便于你在改名、挪目录后仍然保持站点可浏览。",
        "",
        "## 一级目录",
        "",
    ]

    for section_root in iter_note_section_dirs():
        title = section_title(section_root)
        chapter_count = len(section_chapter_dirs(section_root))
        lines.append(
            f"- **{title}**：共 {chapter_count} 个章节，可从 [目录页](../sections/{section_slug(section_root)}) 进入"
        )

    write_markdown(DOCS_DIR / NOTES_DIR / "README.md", "\n".join(lines))


def build_section_pages() -> None:
    for section_root in iter_note_section_dirs():
        section_dir = section_root.name
        title = section_title(section_root)
        chapters = section_chapter_dirs(section_root)
        lines = [
            f"# {title}",
            "",
            "这里汇总当前一级目录下的所有章节，便于从总览快速进入具体笔记。",
            "",
            f"- [查看该目录原始总览](../my-notes/{section_dir}/README.md)",
            "",
            "## 目录导航",
            "",
        ]

        for chapter_dir in chapters:
            chapter_title = first_heading(chapter_dir / "README.md") or pretty_name(chapter_dir.name)
            lines.append(
                f"- [{chapter_title}](../my-notes/{section_dir}/{chapter_dir.name}/README.md)"
            )

        write_markdown(DOCS_DIR / "sections" / section_slug(section_root), "\n".join(lines))


def chapter_slug(section_dir: str, chapter_dir: str) -> str:
    section_prefix = section_dir.split("-", 1)[0]
    return f"{section_prefix}-{chapter_dir}.md"


def build_chapter_pages() -> None:
    for section_root in iter_note_section_dirs():
        section_dir = section_root.name
        for chapter_dir in section_chapter_dirs(section_root):
            article_files = sorted(
                [p for p in chapter_dir.glob("*.md") if p.name.lower() != "readme.md"]
            )
            readme_path = chapter_dir / "README.md"
            title = first_heading(readme_path) or pretty_name(chapter_dir.name)
            lines = [
                f"# {title}",
                "",
                f"- [查看本章总览](../../my-notes/{section_dir}/{chapter_dir.name}/README.md)",
                "",
                "## 本章具体内容",
                "",
            ]

            if not article_files:
                lines.extend(
                    [
                        "这一章当前主要通过总览页进入。",
                        "",
                    ]
                )
            else:
                for article in article_files:
                    lines.append(
                        f"- [{article.stem}](../../my-notes/{section_dir}/{chapter_dir.name}/{article.name})"
                    )

            write_markdown(
                DOCS_DIR / "sections" / "chapters" / chapter_slug(section_dir, chapter_dir.name),
                "\n".join(lines),
            )


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
    ensure_generated_readmes()
    build_notes_overview()
    build_section_pages()
    build_chapter_pages()
    convert_java_tree()


if __name__ == "__main__":
    main()
