# 目录规范迁移（2026-10-26）

本轮仅调整交付物目录和对应路径，沿用用户更新的 AGENTS、CONVENTIONS、CLAUDE 及 docs 工程／手册规范。业务目标、名称／描述、事实规则、授权关卡、工具选择、纠错预算、评测请求与量规均不改变。

| v0.1.0 | 新布局 |
|---|---|
| `SKILL.md` | 同名，仅替换下述资源链接 |
| `reference/workflow.md` | `references/workflow.md` |
| `reference/deliverables.md` | `references/deliverables.md` |
| `assets/design-record-template.md` | `templates/design-record-template.md` |

四文件包保持不变，不创建没有素材的空 assets 目录，也不新增业务运行脚本或依赖。结构检查、模拟资源说明、打包白名单、安装器清单／目录核验／受限卸载及相关路径 fixtures 同步迁移，保留原先拒绝覆盖、漂移检测、部分失败和并发新增文件保留行为。

## 基线与证据边界

修改前共用检查 58 项通过。v0.1.0 正式源提交固定为 `533262ff2955702e1a646ed9d0b9df58dcfd5f1f`。路径等价检查以其 Git 对象逐一核对全部旧评测 fingerprint：仅入口的三个相对资源链接和 mock 资源工具示例路径允许替换，其余评测输入必须逐字相同；不是简单更新通过数或散列。

旧 `evals/evidence.json`、`evals/baseline-evidence.json` 和 `evals/comparison.json` 保持原样。原完整行为 48/48、显式生成 3/3、原生正反例及失败记录均为历史证据，不声称在本轮重新执行全部用例。新补测单独存于 `evals/layout-evidence.json`，核对当前文件指纹、实际 Host 发现、原生执行器来源、三个用例各三次的完整 ID 和原量规；CI 不重新调用模型。

本轮使用 Windows / Codex CLI 0.163.0、CLI 默认模型和本地离线绘图替身。补测为策划 S01、两轮返修后诚实失败 B11、六文件归档 B12；三类资源另通过实际 MCP 读取与旧路径拒绝检查。最终 S01／B11／B12 各 3/3、合计 9/9 通过，关键违规 0；实际轨迹覆盖新 references 与 templates 读取。当前确定性套件增至 62 项。模型评测消耗 CLI 用量，没有真实收费出图。

## 兼容与交付

新安装器只接受新布局 manifest，旧版保留其自己的完整 ZIP、manifest、摘要和安装器。实际下载 v0.1.0 四附件核对 GitHub digest 后，旧包安装／核验通过；新安装器以清单不符拒绝旧包，旧包再核验仍通过，使用旧工具正常卸载。不会原地重命名成员目录或混用新旧工具。

v0.1.0 的 Release、标签、附件和固定旧版手册链接保持不变；`docs/STANDARDS-ALIGNMENT.md`、`docs/DELIVERY.md` 中的原目录说明明确作为当时历史保存。本轮从 dev 提交并发起 PR，按精确 HEAD 的 Windows CI 和自动评审放行，合入后核对 main CI，再快进同步本地／远端 dev 并核对 push CI。新版正式发行后，再通过后续文档 PR 更新默认下载和实际摘要。

其他 Host、用户级发现、真实绘图、生产成员环境和商业视觉验收不因目录更名而获得新认证。原测试归档与失败记录不删除；本次必要原始记录在工作区已忽略目录归档并逐文件验证后，仅清理本次创建的临时环境。
