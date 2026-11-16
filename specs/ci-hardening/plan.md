# PLAN-001 SPEC-001 实施计划

## 改动面（3 个 workflow + 删除 4 个死文件 + 1 个校验脚本）

| 文件 | 需求 | 改动摘要 |
| --- | --- | --- | --- |
| `.github/workflows/k80pro.yml` | R1 R2 R3 R5 R7 R8 | 加 `concurrency`；4 个 job 加 `timeout-minutes`；package 改 `ref: ${{ github.sha }}` + `actions/download-artifact@v6`；`get-ksu-manager` 改为 `needs` 构建产物并传入 `ksu_version`；manifest 用通用正则 + `ksu_version:`；`use_zram` 描述标注 no-op；artifact 保留期 90→30 天 |
| `.github/workflows/build.yml` | R4 R6 R9 | 新增「解析内核侧 KSU 版本」步骤 + job/workflow_call `outputs`；ccache 两步加 5.10/5.15 条件，`mkdir ~/.cache/bazel` 独立保留；bazel/ccache 缓存 key 去掉 sha、改用 `hashFiles`；`repo sync -j4`→`-j8` |
| `.github/workflows/get-manager.yml` | R5 | 新输入 `ksu_version`；`获取 KSU & SUSFS 版本` 优先用该值（跳过全量 clone 与公式）；新增「优先使用官方 Release 的管理器 APK」步骤（versionCode ≤ 内核版本取最大）；`add_KSU` 与上传条件改为「release 路径成功也算成功」 |
| `specs/ci-hardening/verify.py` | AC1–AC9 | 无依赖静态校验（正则/存在性），退出码即验收结果 |
| 删除 | R8 | `zram/`、`susfs-probe.yml`、`deliver.yml`、`deliver_manager.yml` |

## 执行顺序

1. 写 spec/plan/tasks/verify.py（本步）
2. 改 `build.yml`（产出 `ksu_version`，R4/R6/R9）
3. 改 `get-manager.yml`（消费 `ksu_version`，R5）
4. 改 `k80pro.yml`（串起来，R1/R2/R3/R7/R8）
5. `python3 specs/ci-hardening/verify.py` → 全绿
6. 提交 → 推送 `dev`
7. 派发 run #1：验收 RC1（有 APK）、RC3（manifest 同 commit + ksu_version），并检查缓存是否保存
8. 派发 run #2：验收 RC2（`Cache restored from key: bazel-`）+ 时长对比基线 18 分钟

## 关键实现细节

### R4 版本提取（build.yml）
编译步骤已把输出 tee 到 `$GITHUB_WORKSPACE/build-logs/compile-attempt-N.log`，其中含
`-- SukiSU-Nova version: 30000 [v3.0.0-4bec532d@builtin]`。
新步骤取**最新一份**日志：

```bash
NUM=$(grep -oE -- '-- .*version: [0-9]+' "$LOG" | tail -1 | grep -oE '[0-9]+$')
FULL=$(grep -oE -- '\[v[0-9][^]]*\]' "$LOG" | tail -1 | tr -d '[]')
```
回退：从 `bazel-bin/.../Image`（或 `out/.../dist/Image`）里 `strings | grep -m1 -oE 'v[0-9][^ ]*@[a-z]+'` 取 FULL；NUM 取不到则留空（下游走旧逻辑）。

### R5 Release 优先（get-manager.yml）
```
releases?per_page=30 → assets 中匹配 _v<semver>_<code>-release.apk
→ 取 code ≤ TARGET 的最大 code → 下载到 manager-artifacts/<dir>/
```
仓库名同时尝试 `SukiSU-Nova/SukiSU-Nova`（现名）与 `SukiSU-Ultra/SukiSU-Ultra`（旧名，301 跳转）。

### R6 缓存
```yaml
key: bazel-${{ inputs.kernel_version }}-${{ hashFiles('.github/workflows/build.yml') }}
restore-keys: bazel-${{ inputs.kernel_version }}-
```

## 验证命令

```bash
python3 specs/ci-hardening/verify.py          # 静态 AC1–AC9
```
运行时 AC 由真实 run 日志/artifacts 验收（RC1–RC3），记录在 `tasks.md`。
