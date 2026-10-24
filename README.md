# 电商详情页创作 Skill

把 `image-evidence` 中的七张 SOP 教程整理为一个可复用的 Agent Skill：先核实本商品事实，再拆解买家顾虑，为每屏设计画面证据、文案和布局，确认方案后出图，检查并归档。

技能入口：[ecommerce-detailpage-creator](.agents/skills/ecommerce-detailpage-creator/SKILL.md)。原图编号与正确流程的对应、整理补充及证据摘要见 [SOP 来源说明](docs/SOP-SOURCES.md)。

## 文件地图

| 路径 | 用途 |
|---|---|
| `.agents/skills/ecommerce-detailpage-creator/SKILL.md` | 适用范围、核心顺序、授权与结果边界 |
| 技能内 `reference/workflow.md` | 八个策划动作、六屏阅读顺序、验收及返修 |
| 技能内 `reference/deliverables.md` | 事实表、方案卡、逐屏提示词、任务记录及示例 |
| `docs/SOP-SOURCES.md` | 七图核对记录和原图限制 |
| `evals/cases.json`、`evals/RUBRIC.md` | 固定选择／行为场景和人工评测方法 |
| `scripts/check.py`、`tests/test_check.py` | 本地结构检查和检查器失败路径测试 |
| `pyproject.toml`、`uv.lock` | 独立维护环境及锁定的 PyYAML、Pillow |
| `evals/mock_mcp.py`、`scripts/run_behavior_eval.py`、`scripts/grade_behavior_eval.py` | 无网络绘图替身、隔离模型执行与独立评分 |
| `scripts/run_selection_eval.py` | 只暴露名称／描述与原始请求历史的独立选择测试 |
| `evals/evidence.json`、`scripts/audit_evidence.py` | 脱敏的逐次评测结论、版本指纹及一致性检查 |
| `.github/workflows/checks.yml`、`scripts/security_check.py` | PR／main／dev 确定性检查、常见秘密扫描与锁定包 OSV 审查 |
| `scripts/ci_check.py`、`scripts/archive_evidence.py` | 共用检查、失败日志与已关闭评测的逐文件校验归档 |
| `scripts/probe_host.py`、`scripts/skill_snapshot.py` | 原生发现诊断、候选清单及只读漂移核验 |
| `scripts/build_release.py`、`scripts/release_gate.py`、`.github/workflows/release.yml` | 完整 Git SHA 构建、main/dev CI 门禁与预发布草稿 |
| `delivery/Manage-Skill.ps1` | 普通成员本地包校验、拒绝覆盖安装、漂移核验及受限卸载 |
| `docs/OPERATIONS.md` | 实际使用、版本隔离、维护与升级边界 |
| `docs/STANDARDS-ALIGNMENT.md`、`evals/comparison.json` | 新规范差距、最小基线、当前结果与对比限制 |
| `docs/VALIDATION.md` | 验证结果、命令和未验证项 |

## 使用方式

这是纯指令 Skill，日常策划没有 Python 运行时依赖或密钥。首次需将完整技能包安装到目标 Host 的发现位置；已连接的绘图服务另按实际能力与授权使用。技能目录中的入口、`reference/` 及 `assets/` 构成完整运行内容，不依赖发行包外的原图、评测集或本机绝对路径。复制或分发需保持整个技能目录；原图未被附入技能，本文不授予原始教程图片的再分发许可。

在支持读取技能文件的 Agent 中，提供入口和本商品图片、已确认参数、渠道尺寸以及任务范围。例如：

```text
请读取 .agents/skills/ecommerce-detailpage-creator/SKILL.md，
根据我提供的本商品实图和参数策划六屏详情页，先给方案，不提交生成。
```

正常会得到事实表、顾虑映射及分屏方案。缺参数会列待补问题；缺图片不会冒充商品出图。只做主图、SKU 白底图或单图修复时使用对应能力。确认具体方案并授权生成后，才使用宿主已连接的绘图工具，最后交付真实文件和检查结果。

文件位于 `.agents/skills/` 本身不证明宿主可用。本轮已在 Windows / Codex CLI 0.163.0 验证原生仓库发现和模拟任务；没有由此声明其他宿主兼容。实际调用、四文件清单、版本锁定与已知 GitOps 同步缺口见 [使用与维护](docs/OPERATIONS.md)。未修改用户技能目录或宿主配置，未发布版本。

## 维护检查

开发环境使用 Python 3.12+ 与 uv，PyYAML 负责 YAML 解析，Pillow 仅用于绘制合成评测夹具。它们是开发依赖，使用技能策划不需要这些包。先从仓库根准备锁定的独立 `.venv`：

```powershell
uv sync --locked --group dev
```

日常检查复用该环境：

```powershell
uv run --frozen python scripts/ci_check.py
```

以上命令从仓库根执行；`uv run --frozen` 不改锁文件，首次使用前应已完成准备。共用检查将日志归档到 `.eval-runs/ci/`，stdout 为一个 JSON，全通过返回 0，检查失败返回 1；不调用模型或绘图服务，只有安全检查联网查询公共依赖版本。单独结构检查仍为 `python scripts/check.py`，使用安全 YAML 解析、拒绝重复键，检查必需名称／描述和受支持的可选 license／compatibility／metadata、单数 `reference/`、一级引用及正文行数；不冒称支持全部宿主扩展或以长度证明行为合格。

实际模型评测的准备、命令、替身边界及失败诊断见 [评测执行说明](docs/EVAL-HARNESS.md)；量规和固定场景见 `evals/`。这会消耗已登录 Codex 的模型额度，但不调用真实图像供应商。原始回复、PNG 和轨迹写入已忽略的 `.eval-runs/`。

CI 在 Windows / Python 3.12 中运行相同确定性检查，失败时也归档安全日志（7 天），不使用模型凭据、不重跑模型评测。单元测试若缺微软雅黑，可用 Arial 验证文件／协议操作；实际模型看图评测仍要求微软雅黑。Pillow 当前锁定 13.0.0；旧版 12.0.0 及 33 张像素一致的升级检查保留在历史基线记录中，不冒充新版模型推理。

安全检查单独运行 `uv run --frozen python scripts/security_check.py`，通过 OSV 联网查询锁内公共包名和版本，不外发仓库内容；网络或查询异常返回非零。它只覆盖常见秘密格式与 OSV 已收录的包版本问题，不承诺发现所有风险。PR 采用自动代码审查和修复复验，不要求指定人工评审者或人工批准；合并和发布仍需单独授权。

结构校验与人工场景走查不能替代真实模型选择、出图和宿主验收。当前验证状态及交付边界见 [验证记录](docs/VALIDATION.md)。遵守项目约定，Git 提交、推送、PR、合并与发布须取得对应授权。
