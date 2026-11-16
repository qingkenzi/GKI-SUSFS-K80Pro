# TASKS-001 SPEC-001

## 规格
- [x] T1 写 `spec.md`（R1–R9 / AC1–AC9 / 非目标 / 决策记录）
- [x] T2 写 `plan.md`（改动面、顺序、实现细节）
- [x] T3 写 `tasks.md`（本文件）
- [x] T4 写 `verify.py`（无依赖静态校验）

## 实现
- [x] T5 T6 T7 T8 `build.yml`（ccache 条件、稳定缓存 key、ksu_version outputs、repo sync -j8）
- [x] T9 T10 `get-manager.yml`（ksu_version 输入、Release 优先 + `/tags` 双路回退、上传条件）
- [x] T11 T12 T13 `k80pro.yml`（concurrency、超时、github.sha 检出、download-artifact、manifest 修正）
- [x] T14 删除 `zram/`、`susfs-probe.yml`、`deliver.yml`、`deliver_manager.yml`
- [x] T15 `use_zram` 描述标注 no-op（两份入口）

## 验收
- [x] T16 `python3 specs/ci-hardening/verify.py` → AC1–AC9 全绿
- [x] T17 推送 `dev`（`8951f8c` → `269fae2`），派发 run #1/#2/#3
- [x] T18 RC1: run#2/#3 artifacts 含 `SukiSU-Manager(30000)`，APK sha256 `1f2b7a62…0049` = 官方 v3.0.0 包（≤ 30000）✔️
- [x] T19 RC3: run#3 manifest `commit: 269fae2a…` == head sha，含 `ksu_version: v3.0.0-4bec532d@builtin` 与 `ksu_version_num: 30000` ✔️
- [x] T20 RC2: run#3 日志 `Cache restored from key: bazel-6.6-v1`；run#2 曾出现旧 key `bazel-6.6-e69d58b9…`（hashFiles 版本，已按 D3 修正）✔️
- [x] T21 时长对比（见下表）

### 三次构建实测（同一内核源码 commit `612b333c…`）

| run | commit | 缓存 key | bazel 耗时 | 全流程 | 备注 |
|---|---|---|---|---|---|
| 基线 `43846026297` | `017fff8`（旧流程） | `…-bazel-017fff8…`（sha）| 685 s | 18.2 min | 全部 Cache not found |
| #1 `43890824595` | `8951f8c` | `…-hashFiles…` | 686 s | 18.2 min | **RC1 失败**：`/releases` 列表返回空 → 无 APK（触发 R5.1/D4 修正）|
| #2 `43894962375` | `269fae2` | 恢复旧 key → 新存 `bazel-6.6-v1` | 1071 s | 23.6 min | RC1/RC3 通过；key 变更导致一次冷启动（D3 修正依据）|
| #3 `43900435870` | `269fae2` | **`bazel-6.6-v1` 命中** | **656 s** | 18.7 min | 42 disk cache hit；RC1/RC2/RC3 全通过 |

> **基线 vs 稳态**：688 s → 656 s，编译只快约 5%。原因：SukiSU 版本号不再由 CI 固定（改用上游 `builtin` 分支最新提交），每次 `Determining scmversion` 都变，Kleaf 里 284 个 internal action（核心是 `Building kernel`）无法跨构建复用。**结论：Kleaf 的编译瓶颈不在缓存命中，而在源码/版本输入漂移**；若追求极致提速，应固定 KSU 提交（与 `SukiSU(40548/40726)` 变体同样的固定提交机制），届时 disk cache 才能覆盖核心编译 action。当前提速收益主要体现在**可靠性**（APK 获取、可复现、超时、并发互斥、缓存不爆配额）。

## 交付物
- `specs/ci-hardening/spec.md` / `plan.md` / `tasks.md` / `verify.py`
- 4 个 workflow 的改动 + `.yamllint.yml` + `INDEX.md` 更新
- 3 次验收 run：`43890824595` / `43894962375` / `43900435870`

## 当前产物（已推送 delivery）
- boot.md5 `4e1d7ca5…`（run#3 manifest）；`ksu_version_num: 30000`；内核 `6.6.118-android15-8-g612b333c37908-ab10023517-4k`
- 注意：手机上现已刷入 run `43846026297` 的产物（`g86e78ae454f85`），与 delivery 上最新的 run#3 不是同一份。两者同为 SukiSU v3.0.0 / SUSFS v2.4.0，但构建 commit 不同（内核 scmversion 每次变化）。如需对齐，可再刷一次 run#3 的产物。
