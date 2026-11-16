# 文件索引（GitHub 端）

仓库 `qingkenzi/GKI-SUSFS-K80Pro` 的文件地图。**只讲"这堆文件是什么、谁读它、动了会怎样"**，
不讲怎么构建/刷机——那部分在手机端的 `~/roo/K80Pro_GKI_SUSFS_执行方案.md`。

> 上游：`zzh20188/GKI_KernelSU_SUSFS` → fork `qingkenzi/GKI_KernelSU_SUSFS`（Actions 被 GitHub 禁用）
> → 镜像仓（本仓，Actions 可用）。本仓 = **上游本体 + 9 个 K80Pro 专用文件 + `build.yml` 里 1 处补丁**。

## 现状快照

| 分支 | 角色 | 文件数 | 体积 | 末端提交 |
|---|---|---|---|---|
| `dev`（默认） | 全部源码 / workflow / 网页 | 117 | 17.5 MB | `c5b82db0` 2026-11-16 |
| `delivery` | 产物中转：编译好的 `boot.img.xz` | 4 | 10.9 MB | `a7b949a6` 2026-11-16（run 43846026297）|
| `manager` | 产物中转：管理器 APK | 4 | 35.4 MB | `5ef09f8d` 2026-10-23（run 39971742387）|

`delivery` / `manager` 都是 **orphan 分支**，每次构建 `git push -f` 整体覆盖，**不要在上面手改**（改了下次构建就没了）。
GitHub「体积」显示 57 MB ≈ dev 17.5 + delivery 10.9 + manager 35.4（两条产物分支占了 80%）。

## 一、本仓新增的文件（上游没有）

| 文件 | 作用 |
|---|---|
| `.github/workflows/k80pro.yml` | ★ **现行入口**。`resolve-version` → 调 `build.yml` 编译 → 自己用模板打包 `boot.img` → 校验 → 按 `artifact_upload_mode` 上传或推 `delivery` 分支 |
| `.github/workflows/package_only.yml` | 只打包不重编：输入旧 `run_id`，走和 `k80pro.yml` 完全相同的打包逻辑（约 2 分钟）|
| `.yamllint.yml` | 仓库级 yamllint 配置（放开 80 列行长与 `on:` truthy，避免上游长行风格产生噪声）|
| `ci/boot_tpl.bin` | **4 KB 打包模板** = 原厂 1584 B header + AVB vbmeta 2368 B + AVB footer 64 B |
| `ci/boot_tpl.bin.sha256` | 模板哈希（裸哈希，一行）。`cb2da129…32ce5b` |
| `ci/repack_boot_ci.py` | 模板 + 新 `Image` → 96 MB `boot.img`（`--partition-size=100663296`），打包前校验模板 sha256 |
| `ci/make_template.py` | 从**整分区 dump** 重新切出 4 KB 模板，并回写 `.sha256` |
| `ci/repack_boot_v4.py` | 备用打包器（**丢 AVB footer**，本机兜底用，CI 不用）|

旧的 `deliver.yml` / `deliver_manager.yml`、空壳 `susfs-probe.yml` 与死代码 `zram/` 已经删除。
第 10 处改动不是新文件，是 `build.yml` 里的一处补丁，见下节。

## 二、唯一被改过的上游文件：`build.yml`

| | sha256 前 8 | `[K80Pro-fix]` |
|---|---|---|
| 上游原版（= `~/roo/build/build_repo_current.yml`） | `4d774ae5` | 0 处 |
| 本仓 `dev` 现行 | `2035c4b3` | 1 处 |
| 未采用的实验稿（= `~/roo/build/build_prepared_unused.yml`） | `e1ecc566` | 3 处（本仓只要了第 1 处）|

`build.yml` 与上游的差异 = 那 1 处 `[K80Pro-fix]` + 本仓定制
（`ksu_version` outputs、bazel/ccache 缓存 key、ccache 仅 5.10/5.15、`repo sync -j8`）。

那 1 处改动：**`use_zram` 分支里跳过 "ZZH lz4 补丁栈"**（不替换 `lib/lz4/*`、不打 ARMv8 NEON 加速）。
原因：换掉 `lib/lz4` 会让 initramfs 解压走新实现，而本机 ramdisk 是 `lz4_legacy` → 开机解压失败 → **卡 Mi logo**。
另外 2 处实验（`CONFIG_ZRAM_DEF_COMP_LZ4KD` 显式指定、`CONFIG_DEFAULT_FQ_CODEL` 改默认 qdisc）**没推**，留在本地存档里。

改 `build.yml` 之前先对哈希，否则会和上游/本地存档混淆。

## 三、`dev` 顶层清单

| 路径 | 文件数 | 体积 | 是什么 / 谁读它 |
|---|---|---|---|
| `.github/workflows/` | 17 | 0.22 MB | 见第四节 |
| `.github/ISSUE_TEMPLATE/` | 2 | 2 KB | bug / feature 模板（上游）|
| `ci/` | 5 | 0.01 MB | 见第一节，**仅 `k80pro.yml` / `package_only.yml` 读** |
| `config/` | 9 | 1.01 MB | `stock_5.10/5.15/6.1/6.6/6.12.config` 各版本基线 + `config`（通用开关）+ `zram.config` + `SukiSU(40548|40726).config`；`build.yml` 用 `config/stock_${KVER}.config` |
| `data/` | 6 | 21 KB | `androidNN/M.K.json` 版本元数据 + `announcement.json`；`scripts/update_data.py` 写、`web/` 读 |
| `docs/` | 2 | 12 KB | `advanced-features.md` / `-en`（上游高级功能说明）|
| `scripts/` | 5 | 29 KB | `gki_fetch.py` / `fetch_all.py` 拉 AOSP GKI 源码与预编译产物；`susfs_fixes/apply.sh` 打 SUSFS 修复；`update_data.py` / `update_lts.py` 更新 `data/` |
| `security_patch/` | 10 | 34 KB | CVE-2026-43499：`apply_cve_2026_43499.sh` 总入口 + 4 个 rtmutex 版本补丁 + guards patch + `scoped_guard_*`；`build.yml` 在 `cve_2026_43499_patch=true` 时调用 |
| `web/` | 36 | 0.26 MB | GitHub Pages 静态站（`index.html` / `guide.html` + `js/` + `scss/` + webpack）；`update-pages.yml` 部署 |
| `zram/` | ~~10~~ | ~~0.27 MB~~ | **已删除**：死代码，`build.yml` 的 K80Pro-fix 早已跳过拷贝 |
| `assets/` | 8 | 15.56 MB | 上游 README 的图片和 **2 个演示 mp4**（4.8 + 10.4 MB）；仓库体积大头 |
| 根文件 | 7 | 0.03 MB | `README.md`（上游中文自述）/ `README-EN.md` / `LICENSE`（GPL-2.0）/ `CODE_OF_CONDUCT.md` / `.gitattributes` / `.gitignore` / `hmbird_patch.c` |

## 四、14 个 workflow，按角色分四组

**入口（能手动点 / 会上定时跑）**

| 文件 | 名字 | 触发 | 说明 |
|---|---|---|---|
| `k80pro.yml` | K80Pro 定版构建 | dispatch | ★ 现行入口，17 个输入，默认值即定版 |
| `kernel-custom.yml` | Android 内核构建-自定义 | dispatch | `k80pro.yml` 前身，**输入定义与之逐字相同**（同一份 payload 两个入口都吃）|
| `main.yml` | 构建内核 | dispatch | 上游总入口：一次编排 a12~a16 五个版本 + 汇总发布 |
| `kernel-a{12,13,14,15,16}-*.yml` ×5 | 内核构建 - Android X (Y) | dispatch + call | 单版本入口，被 `main.yml` 调用 |
| `package_only.yml` | 仅打包 boot.img | dispatch | 补救用，输入只有 `run_id` |
| `Auto_Trigger.yml` | Auto Trigger on SukiSU Update | cron `0 0 1,16 * *` | 每半月跟一次上游 SukiSU |
| `emergency-cleanup.yml` | Emergency Release Cleanup | dispatch | 清 release 占位 |
| `update-pages.yml` | Update Data & Deploy Pages | cron / dispatch / push | 跑 `scripts/update_data.py` 更新 `data/` 并部署 `web/` |

**被调用（不能直接点）**

| 文件 | 名字 | 触发 | 说明 |
|---|---|---|---|
| `build.yml` | 内核构建流程 | workflow_call | **真正的编译逻辑（86 KB）**，7 个入口都 `uses:` 它；本仓唯一打过补丁的文件 |
| `get-manager.yml` | GetManager | workflow_call | 挑「≤ 内核版本」的最新管理器 APK |

调用链一句话：`main.yml` → `kernel-aXX.yml` → `build.yml` + `get-manager.yml`；
K80Pro 走 `k80pro.yml` / `kernel-custom.yml` → `build.yml` + `get-manager.yml` → 自己打包 `boot.img`。

## 五、两条产物分支里现在是什么

| 分支 | 文件 | 现在的内容 |
|---|---|---|
| `delivery` | `delivery/boot.img.xz`（10.85 MB）、`boot.md5`、`boot.sha256`、`manifest.txt` | run `43846026297`，kernel `6.6.118-android15-8-g86e78ae454f85-ab10020885-4k`，KSU `v3.0.0-4bec532d@builtin`，boot md5 `e00088bf…`（= 手机上已刷入并验证可开机的那份）|
| `manager` | `manager/manager-spoofed.apk`（18.2 MB）+ `.apk.xz`（17.2 MB）+ `.sha256` + `manifest.txt` | run `39971742387`，SukiSU `v4.2.1-r1 / 41055` spoofed 包（比定版用的 `r2 / 41068` 官方包旧）|

`boot.img.xz` 可直接刷；手机端 `tools/fetch_boot.sh` 会读 `boot.sha256` 做校验。
`manager` 同时存了 `.apk` 和 `.apk.xz`（35 MB），只留 xz 能省一半。

## 六、动手前先看这几条

1. **改 `build.yml` 前对齐哈希**：现行 `2035c4b3`，上游原版 `4d774ae5`。搜 `[K80Pro-fix]` 就能看到内核相关的唯一定制点。
2. **`k80pro.yml` 与 `kernel-custom.yml` 的输入完全一样**：改默认值要两份一起改，否则两个入口行为不一致。
3. **`assets/`、`web/`、`config/stock_*.config`、`docs/`、`scripts/` 全是上游的**：动它们会和上游同步冲突，能不改就不改。
6. **`delivery` / `manager` 分支别手改**：force push，改了下次构建就没。
7. **打包模板别手改**：`ci/boot_tpl.bin` 被改动 → `repack_boot_ci.py` 直接报错退出（模板坏 = 镜像不可启动）。要重做就用 `ci/make_template.py`。

## 七、改哪个文件会影响什么

| 想做的事 | 改这里 | 会影响 |
|---|---|---|
| 换内核版本 / 开关（zram、BBG、CVE…）| 不改文件，用 `k80pro.yml` 的 `workflow_dispatch` 输入（或 `~/roo/build/b_*.json` 派发）| 只影响这一次构建 |
| 改编译逻辑 / 补丁顺序 | `.github/workflows/build.yml` | 所有入口、所有版本 |
| 换打包模板 | `ci/make_template.py` 重新生成 + 提交 `boot_tpl.bin` + `.sha256` | 之后所有 `boot.img` |
| 改默认打包大小 / 布局 | `ci/repack_boot_ci.py`（`--partition-size`）| 打包出的镜像 |
| 跟上游 SukiSU / SUSFS | 什么都不改，等 `Auto_Trigger.yml` 定时跑 | `data/` 与构建参数 |
| 网页内容 | `web/` + `data/` | GitHub Pages 站点 |
| 加固 CVE 补丁 | `security_patch/` | `cve_2026_43499_patch=true` 的构建 |
