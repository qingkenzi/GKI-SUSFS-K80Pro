# SPEC-001 CI 流水线加固与提速

- 状态: `accepted` → `implemented` → `verified`
- 适用范围: `.github/workflows/`（K80Pro 定版链路: `k80pro.yml` → `build.yml` + `get-manager.yml` → 打包）
- 基线证据: run `43846026297`（2026-11-16，18 分钟，产物 boot md5 `e00088bf…`，与实机刷入一致）
- 作者/时间: 2026-11-16

## 1. 背景（问题与证据）

| # | 现象 | 证据（来自 run 43846026297 日志） |
| --- | --- | --- | --- |
| P1 | 管理器 APK 永远拿不到 | `KSU_VERSION: 41186` → `未获取到 KSU 版本小于等于 41186 的 Manager artifact` → `上传APK` / `提示 SUSFS 模块下载失败` 均 skipped |
| P2 | 版本号靠公式猜，与内核实际值不一致 | 内核实编为 `SukiSU v3.0.0-4bec532d@builtin` = `30000`；get-manager 却用 main 分支公式算出 `41186` |
| P3 | 打包与内核可能不同源 | `k80pro.yml` package 任务 `ref: dev`，构建期间 `dev` 变化会导致脚本/模板与内核不一致 |
| P4 | 无并发互斥 | 连点两次会并行跑两份，且都会 force push `delivery`，后者覆盖前者 |
| P5 | 部分任务无超时 | `resolve-version` / `package` / `get_ksu_manager` 无 `timeout-minutes`，卡死最多 6 小时 |
| P6 | 缓存实际不命中 | 缓存 key 含 `github.sha` → 每次新 commit 都是新 key；日志 `Cache not found for input keys: android15-6.6-118-bazel-017fff84…`，编译耗时 685 s（占全流程 11.5/18 分钟） |
| P7 | ccache 对 6.6 无效 | `CC="/usr/bin/ccache clang"` 只出现在 5.10/5.15 的 make 路径；6.6 走 Kleaf(bazel)，不经过 ccache |
| P8 | manifest 元数据硬编码 | `grep -o '6\.[0-9]*\.[0-9]*-android15-8[^ ]*'` 写死 `android15-8`；`ksu_version` 靠 `strings` 猜 |
| P9 | 死代码与误导开关 | `zram/`(10 文件 306 KB, 无引用)、`susfs-probe.yml`(空壳)、`deliver.yml`/`deliver_manager.yml`(已被取代)、`use_zram` 输入在 K80Pro 上为 no-op 但仍在 UI 暴露 |

## 2. 目标 / 非目标

**目标**：修复 P1–P5 的正确性与可靠性缺陷；让 P6 缓存真正命中；消除 P8/P9 的隐性坑；全程不改变内核产物语义。

**非目标（明确不做，避免回归）**
- N1 不跟进上游 2026-10-28 ~ 11-16 那 10 个提交（已逐条核验：对 6.6 定版无收益，见 `docs/` 无关；REJECT 与 `PRIORITY_UID_FILTER` 实测已具备）
- N2 不采用上游把 Stock Config 伪装简化为只读 `config/stock_defconfig` 的写法（会静默失去伪装）
- N3 不改 LTO 相关参数（`--config=fast` 已验证可开机）
- N4 不更换 `ci/boot_tpl.bin` 模板
- N5 不动 `web/`、`data/`、`security_patch/`

## 3. 需求（Requirements）

### R1 并发互斥
`k80pro.yml` 必须声明 `concurrency`：group 含 `inputs.kernel_version` 与 `inputs.os_patch_level`，`cancel-in-progress: true`。

### R2 全任务超时
`k80pro.yml` 的每个 job 必须有 `timeout-minutes`（`resolve-version` ≤ 10，`package` ≤ 25）。

### R3 打包可复现
`package` 任务必须检出**本次 dispatch 的 commit**（`${{ github.sha }}`），不得检出可变分支；内核产物必须用 `actions/download-artifact` 拉取（同一 run，排除跨 run 串包）。

### R4 KSU 版本唯一真源
内核侧 KSU 数字版本必须来自**构建产物自身**（编译日志中的 `-- <NAME> version: <N>` 行，缺失时回退到 Image 字符串），由 `build.yml` 通过 job output 暴露；`get-manager` 优先使用该值，只有未提供时才回退旧公式。

### R5 管理器获取顺序
获取管理器 APK 必须**先查 GitHub Release 资产**（文件名形如 `*_v<semver>_<versionCode>-release.apk`，取 `versionCode ≤ 内核版本` 的最大值），失败才回退到「扫描 Actions 产物」的旧路径；两条路径都不改变 `manager` 分支语义。

### R6 缓存有效
bazel 磁盘缓存与 ccache 的 key 不得包含 `github.sha`；bazel key 必须含配置维度与 `hashFiles('.github/workflows/build.yml')`，并保留前缀 `restore-keys`。ccache 的配置/恢复步骤只在 `5.10`/`5.15` 生效，而 `~/.cache/bazel` 目录准备对全部版本保留。

### R7 manifest 元数据
打包 manifest 必须包含 `ksu_version`（来自 R4 的 output）；内核版本串正则不得硬编码 `androidNN-N`。

### R8 仓库卫生
删除无引用/空壳文件：`zram/`、`.github/workflows/susfs-probe.yml`、`.github/workflows/deliver.yml`、`.github/workflows/deliver_manager.yml`；`k80pro.yml` 与 `kernel-custom.yml` 中 `use_zram` 输入描述必须标注 K80Pro 上为 no-op（两处保持一致）。

### R9 源码同步并行度
`build.yml` 的 `repo sync` 并行度 ≥ 8。

## 4. 验收标准（Acceptance Criteria）

### 静态（`python3 specs/ci-hardening/verify.py`，必须全绿）
- AC1 满足 R1：`k80pro.yml` 含 concurrency 且 group 引用 `inputs.kernel_version`
- AC2 满足 R2：`k80pro.yml` 的 4 个 job 均有 `timeout-minutes`
- AC3 满足 R3：package 的 `ref` 为 `${{ github.sha }}`，且使用 `actions/download-artifact@`
- AC4 满足 R4：`build.yml` 声明 `outputs.ksu_version`，且存在解析 `version: <N>` 的步骤
- AC5 满足 R5：`get-manager.yml` 含 release 资产解析与 `ksu_version` 输入；`k80pro.yml` 传入 `needs.*.outputs.ksu_version`
- AC6 满足 R6：缓存 key 不含 `github.sha`；bazel key 含 `hashFiles`；ccache 步骤带 5.10/5.15 条件
- AC7 满足 R7：manifest 段含 `ksu_version:`，KREL 正则不含 `android15-8`
- AC8 满足 R8：死文件不存在；两份入口的 `use_zram` 描述一致且标注 no-op
- AC9 满足 R9：`repo sync` 并行度 ≥ 8

### 运行时（一次真实构建 run）
- RC1 该 run 的 artifacts 中**存在管理器 APK**，且其 versionCode ≤ 内核 KSU 版本（`30000`）
- RC2 连续第二次 run 的日志出现 `Cache restored from key: bazel-`
- RC3 打包 manifest 的 `commit:` 等于该 run 的 head sha，且含 `ksu_version:`

## 5. 风险与回滚

| 风险 | 缓解 |
| --- | --- | --- | --- |
| `get-manager` 改造后 AVK 上传条件写错 | 保留旧路径为 fallback；RC1 直接验收 |
| `download-artifact` 名称模式不匹配 | 用 `pattern: '*_kernel-*'` + `find` 定位 zip，不依赖 `env.CONFIG` |
| build.yml 新增 outputs 影响其他 7 个入口 | 纯追加，其他入口不消费；`main.yml`/`kernel-a*.yml` 不传 `ksu_version` 时走旧逻辑 |
| 缓存 key 变更导致首次 run 仍冷启动 | RC2 以第二次 run 为准 |

回滚：`git revert <merge-commit>`；内核产物不受影响（本 spec 不改编译参数）。

## 6. 决策记录

- **D1 不做上游同步**：逐条核验后确认对 6.6/Android15 定版零收益（详见上文 N1）。
- **D2 版本以产物为准**：公式法在不同分支（main vs builtin）会得到不同数量级的结果，是 P1/P2 的根因。
- **D3 缓存 key 用 `hashFiles(build.yml)` 而非 sha**：Kleaf `--disk_cache` 是内容寻址的，跨 commit 复用安全；用 sha 只会制造垃圾缓存并挤爆 10 GB 配额。
