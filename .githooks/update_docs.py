#!/usr/bin/env python3
"""
.githooks/update_docs.py

Git hooks 自动文档更新脚本。
由 post-commit / prepare-commit-msg 调用。

功能：
1. 检测文件变更（新增/删除/移动模块）
2. 变更 MODULES.md：新增模块入口、结构变化时重写目录树
3. 变更 CHANGELOG.md：追加本次提交的文件变更摘要

用法：
    python3 .githooks/update_docs.py <commit_msg_file> [commit_type]
    python3 .githooks/update_docs.py --modules-only
    python3 .githooks/update_docs.py --changelog-only "<msg>"
"""

import subprocess
import sys
import os
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODULES_FILE = PROJECT_ROOT / "MODULES.md"
CHANGELOG_FILE = PROJECT_ROOT / "CHANGELOG.md"


def run(cmd: str) -> str:
    """执行 git 命令并返回输出"""
    return subprocess.check_output(cmd, shell=True, cwd=PROJECT_ROOT,
                                  stderr=subprocess.DEVNULL).decode("utf-8").strip()


def get_changed_files() -> list:
    """获取本次提交变更的文件列表"""
    try:
        # HEAD~1 -> HEAD 的变更文件
        output = run("git diff --name-status HEAD~1 HEAD")
        if not output:
            # 首次提交
            output = run("git ls-files")
            return [(f"?? {line}", line) for line in output.splitlines()]
        return [tuple(line.split("\t", 1)) for line in output.splitlines()]
    except Exception:
        return []


def detect_module_changes(files: list) -> dict:
    """
    分析变更文件，返回变更摘要。
    返回结构：
    {
        'new_modules': [...],
        'modified_modules': [...],
        'new_dirs': [...],
        'deleted_modules': [...],
    }
    """
    result = {
        'new_modules': [],
        'modified_modules': [],
        'new_dirs': [],
        'deleted_modules': [],
    }
    for status, path in files:
        path = path.strip()
        if status.startswith("??"):  # 新文件/未跟踪
            if _is_module_file(path):
                result['new_modules'].append(path)
            if _is_new_dir(path):
                result['new_dirs'].append(path)
        elif status == "D":  # 删除
            if _is_module_file(path):
                result['deleted_modules'].append(path)
        elif status in ("M", "A", "R", "C"):  # 修改/新增/重命名/复制
            if _is_module_file(path):
                if status == "A":
                    result['new_modules'].append(path)
                else:
                    result['modified_modules'].append(path)

        # MODULES.md / CHANGELOG.md 本身变更，不递归
        if path in ("MODULES.md", "CHANGELOG.md"):
            result['modified_modules'] = [p for p in result['modified_modules'] if p != path]
            result['new_modules'] = [p for p in result['new_modules'] if p != path]

    return result


def _is_module_file(path: str) -> bool:
    """判断是否为需要记录的模块文件"""
    skip = {".git", "node_modules", "__pycache__", ".venv", ".gitignore",
            "MODULES.md", "CHANGELOG.md", ".DS_Store", "requirements.txt",
            "run.sh", "启动"}
    return not any(s in path for s in skip) and (
        path.endswith(".py") or path.endswith(".vue") or
        path.endswith(".js") or path.endswith(".mjs") or
        path.endswith(".css") or path.endswith(".html") or
        path.endswith(".json") or path.endswith(".md")
    )


def _is_new_dir(path: str) -> bool:
    """判断是否新增了目录（第一层目录结构变更）"""
    return "/" in path and not path.startswith("vue-project/src/")


def update_changelog(summary: str, detail: str = ""):
    """
    向 CHANGELOG.md 追加未分类条目。
    策略：追加到 [Unreleased] 或最新版本下。
    """
    if not CHANGELOG_FILE.exists():
        return

    content = CHANGELOG_FILE.read_text(encoding="utf-8")

    today = datetime.now().strftime("%Y-%m-%d")

    # 查找是否有 [Unreleased] 区块
    unreleased_pattern = re.compile(r"(## \[Unreleased\].*?\n)(.*?)(?=\n## |\Z)", re.DOTALL)
    match = unreleased_pattern.search(content)

    if match:
        # 追加到 Unreleased
        header = match.group(1)
        body = match.group(2).rstrip()
        rest = content[match.end():]

        new_entry = f"- **{summary}**"
        if detail:
            new_entry += f" — {detail}"
        new_entry += "\n"

        new_body = body + "\n" + new_entry
        new_content = content[:match.start(1)] + header + new_body + "\n" + rest
    else:
        # 在最新版本前插入 Unreleased
        first_version = re.search(r"(## \[)", content)
        if first_version:
            pos = first_version.start()
            new_section = (
                f"## [Unreleased]\n\n### Changed\n"
                f"- **{summary}**"
                + (f" — {detail}" if detail else "")
                + "\n\n"
            )
            new_content = content[:pos] + new_section + content[pos:]
        else:
            new_content = content  # 保持不变

    CHANGELOG_FILE.write_text(new_content, encoding="utf-8")


def update_modules_summary(change_info: dict):
    """
    在 MODULES.md 底部追加本次变更摘要（追加模式，不重写）。
    """
    if not MODULES_FILE.exists():
        return

    summary_lines = []
    today = datetime.now().strftime("%Y-%m-%d")
    summary_lines.append(f"\n<!-- auto-updated {today} -->")

    if change_info['new_modules']:
        summary_lines.append("\n### 新增模块\n")
        for m in sorted(set(change_info['new_modules'])):
            summary_lines.append(f"- `{m}`")

    if change_info['modified_modules']:
        summary_lines.append("\n### 更新模块\n")
        for m in sorted(set(change_info['modified_modules'])):
            summary_lines.append(f"- `{m}`")

    if change_info['deleted_modules']:
        summary_lines.append("\n### 删除模块\n")
        for m in sorted(set(change_info['deleted_modules'])):
            summary_lines.append(f"- ~~`{m}`~~")

    if len(summary_lines) == 1:
        return  # 无实质变更

    with open(MODULES_FILE, "a", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))


def main():
    args = sys.argv[1:]

    # 解析参数
    modules_only = "--modules-only" in args
    changelog_only = False
    commit_msg_file = None

    if modules_only:
        files = get_changed_files()
        change_info = detect_module_changes(files)
        update_modules_summary(change_info)
        return

    for i, arg in enumerate(args):
        if arg in ("--modules-only", "--changelog-only"):
            args.pop(i)
            break

    if args:
        commit_msg_file = args[0]

    # 获取变更文件
    try:
        files = get_changed_files()
    except Exception:
        return

    if not files:
        return

    change_info = detect_module_changes(files)

    # 更新 MODULES.md
    if change_info['new_modules'] or change_info['modified_modules'] or change_info['deleted_modules']:
        update_modules_summary(change_info)

    # 更新 CHANGELOG.md
    if not modules_only:
        all_changed = (change_info['new_modules'] +
                       change_info['modified_modules'] +
                       change_info['deleted_modules'])
        if all_changed:
            # 从 commit msg 提取第一行作为摘要
            summary = "项目变更自动记录"
            detail = ", ".join(sorted(set(all_changed))[:5])
            if len(all_changed) > 5:
                detail += f" 等共{len(all_changed)}个文件"
            if commit_msg_file and os.path.exists(commit_msg_file):
                with open(commit_msg_file, "r", encoding="utf-8") as f:
                    first_line = f.readline().strip().strip("#").strip()
                    if first_line:
                        summary = first_line

            update_changelog(summary, detail)


if __name__ == "__main__":
    main()
