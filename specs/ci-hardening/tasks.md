# TASKS-001 SPEC-001

## 规格
- [x] T1 写 `spec.md`（R1–R9 / AC1–AC9 / 非目标 / 决策记录）
- [x] T2 写 `plan.md`（改动面、顺序、实现细节）
- [x] T3 写 `tasks.md`（本文件）
- [x] T4 写 `verify.py`（无依赖静态校验）

## 实现
- [ ] T5 `build.yml`: ccache 步骤加 5.10/5.15 条件 + `mkdir ~/.cache/bazel` 独立
- [ ] T6 `build.yml`: 缓存 key 去 sha、改 `hashFiles`
- [ ] T7 `build.yml`: 新增「解析内核侧 KSU 版本」+ job/workflow_call outputs
- [ ] T8 `build.yml`: `repo sync -j8`
- [ ] T9 `get-manager.yml`: 新输入 `ksu_version` + 优先使用 + 跳过公式
- [ ] T10 `get-manager.yml`: Release 资产优先路径 + 上传条件
- [ ] T11 `k80pro.yml`: `concurrency` + 4 个 `timeout-minutes`
- [ ] T12 `k80pro.yml`: `get-ksu-manager` 接 `needs` 与 `ksu_version`
- [ ] T13 `k80pro.yml`: package `ref: github.sha` + `download-artifact` + manifest 修正
- [ ] T14 删除 `zram/`、`susfs-probe.yml`、`deliver.yml`、`deliver_manager.yml`
- [ ] T15 `use_zram` 描述标注 no-op（`k80pro.yml` + `kernel-custom.yml`）

## 验收
- [ ] T16 `python3 specs/ci-hardening/verify.py` → AC1–AC9 全绿
- [ ] T17 推送 `dev`，派发 run #1
- [ ] T18 RC1: artifacts 含管理器 APK，versionCode ≤ 30000
- [ ] T19 RC3: manifest `commit:` == run head sha，且含 `ksu_version:`
- [ ] T20 派发 run #2，RC2: 日志出现 `Cache restored from key: bazel-`
- [ ] T21 记录 run #1/#2 时长与基线 run `43846026297`（18 分钟）对比

## 交付物
- `specs/ci-hardening/spec.md` / `plan.md` / `tasks.md` / `verify.py`
- 3 个 workflow 的改动
- 上述验收记录
