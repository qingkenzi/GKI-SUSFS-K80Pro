#!/usr/bin/env python3
"""SPEC-001 静态验收检查（无第三方依赖）。

用法:
    python3 specs/ci-hardening/verify.py

逐条校验 AC1–AC9，全部通过时退出码 0；任何一条失败打印原因并退出码 1。
运行时验收（RC1–RC3）需要真实构建 run，记录在 specs/ci-hardening/tasks.md。
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WF = os.path.join(ROOT, ".github", "workflows")


# ---------------------------------------------------------------- 基础工具
def read(rel: str) -> str:
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def wf(name: str) -> str:
    return read(os.path.join(".github", "workflows", name))


def jobs_of(text: str) -> dict[str, str]:
    """粗切 jobs: 下的顶层 job 块（2 空格缩进的 key）。"""
    m = re.search(r"^jobs:\n", text, re.M)
    if not m:
        return {}
    blocks: dict[str, list[str]] = {}
    cur: str | None = None
    for line in text[m.end():].splitlines():
        mj = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if mj:
            name = mj.group(1)
            cur = name
            blocks[name] = []
            continue
        if cur and re.match(r"^[^\s#]", line):
            cur = None
            continue
        if cur is not None and line.strip():
            blocks[cur].append(line)
    return {k: "\n".join(v) for k, v in blocks.items()}


# ---------------------------------------------------------------- 各项检查
def ac1(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R1: 并发互斥。"""
    ok = (
        re.search(r"^concurrency:", k80, re.M) is not None
        and re.search(r"group:.*inputs\.kernel_version", k80) is not None
        and re.search(r"cancel-in-progress:\s*true", k80) is not None
    )
    return ok, "k80pro.yml 有 concurrency(group 含 kernel_version) + cancel-in-progress"


def ac2(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R2: 全任务超时（reusable-workflow 任务由被调用侧限制，豁免）。"""
    kjobs = jobs_of(k80)
    missing = [
        n for n, body in kjobs.items()
        if "timeout-minutes:" not in body and re.search(r"^    uses:", body, re.M) is None
    ]
    mgr_timeout = re.search(r"timeout-minutes:\s*\d+", mgr) is not None
    ok = not missing and len(kjobs) >= 4 and mgr_timeout
    return ok, (
        f"k80pro jobs={list(kjobs)} 缺超时={missing or '无'}；get-manager job 有超时={mgr_timeout}"
    )


def ac3(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R3: 打包可复现。"""
    pkg = jobs_of(k80).get("package", "")
    ok = (
        "ref: ${{ github.sha }}" in pkg
        and re.search(r"actions/download-artifact@v\d+", pkg) is not None
        and "ref: dev" not in k80
    )
    return ok, "package 用 github.sha 检出 + actions/download-artifact，且无 ref: dev"


def ac4(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R4: KSU 版本以构建产物为准。"""
    ok = (
        re.search(r"^\s+ksu_version:\s*$", build, re.M) is not None
        and "jobs.build-kernel.outputs.ksu_version" in build
        and "version: [0-9]+" in build
        and "compile-attempt-" in build
    )
    return ok, "build.yml 声明 outputs.ksu_version 且从编译日志解析 'version: N'"


def ac5(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R5: 管理器 Release 资产优先 + 调用侧传参。"""
    ok = (
        re.search(r"ksu_version:\s*\n\s+required:\s*false", mgr) is not None
        and re.search(r"releases\?per_page=", mgr) is not None
        and re.search(r"-release\\\\?\.apk", mgr) is not None
        and re.search(r"ksu_version:\s*\$\{\{\s*needs\.[a-z-]+\.outputs\.ksu_version", k80) is not None
        and re.search(r"get-ksu-manager:\s*\n\s+needs:", k80) is not None
    )
    return ok, "get-manager 有 ksu_version 输入 + Release 资产优先；k80pro 传入 needs 输出"


def ac6(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R6: 缓存 key 稳定且按版本区分。"""
    bad_key = re.search(r"^\s+key:.*(bazel|ccache).*github\.sha", build, re.M)
    ok = (
        bad_key is None
        and re.search(r"key: bazel-\$\{\{ inputs\.kernel_version \}\}-\$\{\{ hashFiles\(", build) is not None
        and re.search(
            r"restore-keys:\s*\|?\s*\n\s+bazel-\$\{\{ inputs\.kernel_version \}\}-", build
        ) is not None
        and len(re.findall(r"kernel_version == '5\.10' \|\| inputs\.kernel_version == '5\.15'", build)) >= 2
    )
    return ok, "缓存 key 不含 github.sha；bazel key 含 hashFiles + 前缀 restore；ccache 限 5.10/5.15"


def ac7(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R7: manifest 元数据。"""
    pkg = jobs_of(k80).get("package", "")
    ok = (
        "ksu_version:" in pkg
        and "android15-8" not in pkg
        and re.search(r"android\[0-9\]\+", pkg) is not None
    )
    return ok, "manifest 含 ksu_version: 且内核版本串正则不硬编码 android15-8"


def ac8(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R8: 仓库卫生。"""
    dead = [
        "zram",
        ".github/workflows/susfs-probe.yml",
        ".github/workflows/deliver.yml",
        ".github/workflows/deliver_manager.yml",
    ]
    still = [d for d in dead if os.path.exists(os.path.join(ROOT, d))]
    ok = not still and "no-op" in k80 and "no-op" in custom
    return ok, f"死文件残留={still or '无'}；use_zram 两处标注 no-op"


def ac9(k80: str, build: str, mgr: str, custom: str) -> tuple[bool, str]:
    """R9: 源码同步并行度 ≥ 8。"""
    m = re.search(r'SYNC_FLAGS="-c -j(\d+)', build)
    return bool(m) and int(m.group(1)) >= 8, f"repo sync 并行度 = {m.group(1) if m else '未找到'}（要求 ≥ 8）"


CHECKS = [ac1, ac2, ac3, ac4, ac5, ac6, ac7, ac8, ac9]


def main() -> int:
    ctx = {
        "k80": wf("k80pro.yml"),
        "build": wf("build.yml"),
        "mgr": wf("get-manager.yml"),
        "custom": wf("kernel-custom.yml"),
    }
    print("SPEC-001 静态验收")
    failed: list[str] = []
    for fn, ac in zip(CHECKS, [f"AC{i}" for i in range(1, 10)]):
        ok, detail = fn(**ctx)
        print(f"  {'PASS' if ok else 'FAIL'} {ac:<4} {detail}")
        if not ok:
            failed.append(f"{ac}: {detail}")

    print()
    if failed:
        print(f"结果: FAIL（{len(failed)} 条未满足）")
        for f in failed:
            print(f"  - {f}")
        return 1
    print("结果: PASS（AC1–AC9 全部满足）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
