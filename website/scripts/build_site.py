from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = ROOT / ".site-docs"
NOTES_DIR = "my-notes"
JAVA_SOURCE_DIR = "solutions-java"

SECTION_PAGES = {
    "01-基础巩固": {
        "slug": "foundation-basics.md",
        "title": "基础巩固",
        "summary": "从数据结构、排序、链表、树、递归到动态规划，适合作为算法体系的第一阶段。",
        "intro": "这里更偏“打地基”。如果你希望把常见面试题背后的基础模块真正串起来，这一部分最适合慢慢啃。",
        "items": [
            ("01 选择排序、二分法、异或运算", "01-选择排序-二分法-异或运算"),
            ("02 链表、栈、队列、递归行为、哈希表、有序表", "02-链表-队列-栈-哈希表-递归复杂度"),
            ("03 归并排序、随机快排", "03-归并排序-随机快排"),
            ("04 堆、比较器", "04-堆排序-优先级队列"),
            ("05 前缀树、桶排序、排序总结", "05-非比较排序-排序总结"),
            ("06 链表相关面试题", "06-链表相关面试题"),
            ("07 二叉树的基本算法", "07-二叉树的基本算法"),
            ("08 二叉树的递归套路", "08-二叉树的递归套路"),
            ("09 数据归纳与矩阵处理技巧", "09-数据归纳与矩阵处理技巧"),
            ("10 并查集结构和图相关的算法", "10-图论铺垫-贪心算法-并查集"),
            ("11 图相关的算法", "11-图相关的算法"),
            ("12 暴力递归到动态规划1-递归尝试", "12-暴力递归到动态规划1-递归尝试"),
            ("13 暴力递归到动态规划2-尝试模型", "13-暴力递归到动态规划2-尝试模型"),
            ("14 暴力递归到动态规划2-暴力递归改动态规划", "14-暴力递归到动态规划2-暴力递归改动态规划"),
            ("15 暴力递归到动态规划3-动态规划的进一步优化", "15-暴力递归到动态规划3-动态规划的进一步优化"),
        ],
    },
    "02-基础提升": {
        "slug": "foundation-advanced.md",
        "title": "基础提升",
        "summary": "进入专题化训练阶段，开始系统接触哈希、并查集、KMP、单调栈、Morris 遍历等常见进阶主题。",
        "intro": "这一部分更适合在基础打稳以后看，它不是单题训练，而是按专题去建立“工具箱”。",
        "items": [
            ("01 哈希函数与哈希表", "01-哈希函数-哈希表"),
            ("02 有序表、并查集", "02-并查集"),
            ("03 KMP、Manacher 算法", "03-KMP-Manacher算法"),
            ("04 滑动窗口、单调栈结构等", "04-滑动窗口-单调栈结构等"),
            ("05 二叉树的 Morris 遍历", "05-二叉树的Morris遍历"),
            ("06 大数据题目", "06-大数据题目"),
            ("07 暴力递归", "07-暴力递归"),
        ],
    },
    "03-中级提升": {
        "slug": "intermediate.md",
        "title": "中级提升",
        "summary": "更贴近综合题和真实面试表达，适合在完成基础训练后，做方法串联和题感提升。",
        "intro": "如果你已经不满足于“会做题”，而想进一步建立题型迁移能力，这一部分会更有帮助。",
        "items": [
            ("01 题目 1 LRU", "01-题目1-LRU.md"),
            ("02 题目 2 中等难度", "02-题目2-中等难度.md"),
            ("03 题目 3 跳步问题", "03-题目3-跳步问题.md"),
            ("04 题目 4 力扣原题", "04-题目4-力扣原题.md"),
        ],
    },
    "09-大厂真题": {
        "slug": "big-tech.md",
        "title": "大厂真题",
        "summary": "按更接近真实面试场景的方式整理题目，用于把前面的知识体系迁移到面试实战中。",
        "intro": "这一部分更适合在前面内容看过一轮以后回头刷，能更清楚地感受到知识点在真实题目中的组合方式。",
        "items": [
            ("01 题目 1", "01-题目1.md"),
            ("02 题目 2", "02-题目2.md"),
            ("03 题目 3", "03-题目3.md"),
            ("04 题目 4", "04-题目4.md"),
            ("05 题目 5", "05-题目5.md"),
            ("06 题目 6", "06-题目6.md"),
        ],
    },
}

CHAPTER_SECTION_DIRS = ("01-基础巩固", "02-基础提升")


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
    content = """# 我的算法笔记

> 一个围绕 `my-notes` 持续整理的个人算法学习站点。

这里不是单纯堆题解的地方，而更像一份按学习路径整理出来的算法知识地图：

- 用中文语境梳理算法知识体系
- 保留从基础到进阶的阅读顺序
- 把系统笔记、专题方法和面试题感放在同一条成长线上

## 从这里开始

<div class="grid cards" markdown>

-   **基础巩固**

    ---

    从排序、链表、二叉树、递归到动态规划，适合先把地基打稳。

    [进入这一部分](sections/foundation-basics.md)

-   **基础提升**

    ---

    按专题补强常见算法工具箱，比如 KMP、并查集、单调栈、Morris。

    [进入这一部分](sections/foundation-advanced.md)

-   **中级提升**

    ---

    更偏综合应用和面试表达，适合在基础题型熟悉后继续往上走。

    [进入这一部分](sections/intermediate.md)

-   **大厂真题**

    ---

    把前面的知识点放进真实面试场景里，看组合、看变化、看套路。

    [进入这一部分](sections/big-tech.md)

</div>

## 推荐阅读顺序

1. 如果你刚开始补算法，建议先从 [基础巩固](sections/foundation-basics.md) 开始。
2. 看完一轮基础内容，再进入 [基础提升](sections/foundation-advanced.md) 建立专题工具箱。
3. 接着用 [中级提升](sections/intermediate.md) 训练综合题感和表达方式。
4. 最后结合 [大厂真题](sections/big-tech.md) 去接近真实面试节奏。

## 这个站点更适合谁

- 想系统补算法，而不是只零散刷题的人
- 想把“题目”连成“知识体系”的人
- 更习惯中文笔记、中文导图、中文面试表达的人

## 快速入口

- [笔记总览](my-notes/README.md)
- [基础巩固总览](my-notes/01-基础巩固/README.md)
- [基础提升总览](my-notes/02-基础提升/README.md)
- [中级提升总览](my-notes/03-中级提升/README.md)
- [大厂真题总览](my-notes/09-大厂真题/README.md)
"""
    write_markdown(DOCS_DIR / "index.md", content)


def build_section_pages() -> None:
    for section_dir, meta in SECTION_PAGES.items():
        slug = meta["slug"]
        title = meta["title"]
        summary = meta["summary"]
        intro = meta["intro"]
        lines = [
            f"# {title}",
            "",
            summary,
            "",
            intro,
            "",
            f"- [查看该目录原始总览](../my-notes/{section_dir}/README.md)",
            "",
            "## 目录导航",
            "",
        ]

        section_root = ROOT / NOTES_DIR / section_dir
        for chapter_dir in sorted(p for p in section_root.iterdir() if p.is_dir()):
            chapter_title = first_heading(chapter_dir / "README.md") or pretty_name(chapter_dir.name)
            lines.append(
                f"- [{chapter_title}](../my-notes/{section_dir}/{chapter_dir.name}/README.md)"
            )

        write_markdown(DOCS_DIR / "sections" / slug, "\n".join(lines))


def chapter_slug(section_dir: str, chapter_dir: str) -> str:
    section_prefix = section_dir.split("-", 1)[0]
    return f"{section_prefix}-{chapter_dir}.md"


def build_chapter_pages() -> None:
    for section_dir in CHAPTER_SECTION_DIRS:
        section_root = ROOT / NOTES_DIR / section_dir
        for chapter_dir in sorted([p for p in section_root.iterdir() if p.is_dir()]):
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
    build_section_pages()
    build_chapter_pages()
    convert_java_tree()


if __name__ == "__main__":
    main()
