# 电商详情页创作 Skill

把 `image-evidence` 中的七张 SOP 教程整理为一个可复用的 Agent Skill：先核实本商品事实，再拆解买家顾虑，为每屏设计画面证据、文案和布局，确认方案后出图，检查并归档。

技能入口：[ecommerce-detailpage-creator](.agents/skills/ecommerce-detailpage-creator/SKILL.md)。原图编号与正确流程的对应、整理补充及证据摘要见 [SOP 来源说明](docs/SOP-SOURCES.md)。

## 文件地图

| 路径 | 用途 |
|---|---|
| `.agents/skills/ecommerce-detailpage-creator/SKILL.md` | 适用范围、核心顺序、授权与结果边界 |
| 技能内 `references/workflow.md` | 八个策划动作、六屏阅读顺序、验收及返修 |
| 技能内 `references/deliverables.md` | 事实表、方案卡、逐屏提示词、任务记录及示例 |
| `docs/SOP-SOURCES.md` | 七图核对记录和原图限制 |
| `evals/cases.json`、`evals/RUBRIC.md` | 固定选择／行为场景和人工评测方法 |
| `scripts/check.py`、`tests/test_check.py` | 本地结构检查和检查器失败路径测试 |
| `pyproject.toml`、`uv.lock` | 独立维护环境及锁定的 PyYAML、Pillow |
| `evals/mock_mcp.py`、`scripts/run_behavior_eval.py`、`scripts/grade_behavior_eval.py` | 无网络绘图替身、隔离模型执行与独立评分 |
| `scripts/run_selection_eval.py` | 只暴露名称／描述与原始请求历史的独立选择测试 |
| `evals/evidence.json`、`scripts/audit_evidence.py` | 脱敏的逐次评测结论、版本指纹及一致性检查 |
| `.github/workflows/checks.yml`、`scripts/security_check.py` | PR／main 确定性检查、常见秘密扫描与锁定包 OSV 审查 |
| `docs/VALIDATION.md` | 验证结果、命令和未验证项 |

## 使用方式

这是纯指令 Skill，日常策划没有运行时依赖、密钥或安装步骤。技能目录中的入口及 `references/` 构成完整运行内容，不依赖发行包外的原图、评测集或本机绝对路径。复制或分发需保持整个技能目录；原图未被附入技能，本文不授予原始教程图片的再分发许可。

在支持读取技能文件的 Agent 中，提供入口和本商品图片、已确认参数、渠道尺寸以及任务范围。例如：

```text
请读取 .agents/skills/ecommerce-detailpage-creator/SKILL.md，
根据我提供的本商品实图和参数策划六屏详情页，先给方案，不提交生成。
```

正常会得到事实表、顾虑映射及分屏方案。缺参数会列待补问题；缺图片不会冒充商品出图。只做主图、SKU 白底图或单图修复时使用对应能力。确认具体方案并授权生成后，才使用宿主已连接的绘图工具，最后交付真实文件和检查结果。

文件位于 `.agents/skills/` 不作为任何宿主已发现、已安装或兼容的证明。本次只交付工作区实现；未修改用户技能目录或宿主配置，也未发布版本。需要宿主安装时，按所选产品与版本另行核对发现、刷新和调用方式。升级或移除副本前先比较并保留自定义内容及业务素材，不清空共享目录。

## 维护检查

开发环境使用 Python 3.12+ 与 uv，PyYAML 负责 YAML 解析，Pillow 仅用于绘制合成评测夹具。它们是开发依赖，使用技能策划不需要这些包。先从仓库根准备锁定的独立 `.venv`：

```powershell
uv sync --locked --group dev
```

日常检查复用该环境：

```powershell
uv run --frozen python scripts/check.py
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python scripts/audit_evidence.py
```

以上相对命令从仓库根执行；`uv run --frozen` 不改锁文件，首次使用前应已完成准备。检查成功返回 0，缺文件、链接越界、元数据或场景错误返回 1；输入与输出采用 UTF-8，不修改业务文件，不联网或调用绘图服务。检查器使用安全 YAML 解析并拒绝重复键，项目 frontmatter 当前限定 `name` 和 `description`，不冒称支持所有开放格式扩展。未发生原图修改时无需重复核对图像摘要；摘要可用 `Get-FileHash -Algorithm SHA256` 对照来源说明。

实际模型评测的准备、命令、替身边界及失败诊断见 [评测执行说明](docs/EVAL-HARNESS.md)；量规和固定场景见 `evals/`。这会消耗已登录 Codex 的模型额度，但不调用真实图像供应商。原始回复、PNG 和轨迹写入已忽略的 `.eval-runs/`。

CI 在 Windows / Python 3.12 中运行相同结构、单元及证据一致性检查，不使用模型凭据、不重跑模型评测。单元测试若缺微软雅黑，可用 Arial 验证文件／协议操作；实际模型看图评测仍要求微软雅黑。Pillow 当前锁定 13.0.0；旧模型证据使用的 12.0.0 保留为历史环境，已核对升级前后全部 33 张种子夹具像素一致。

安全检查单独运行 `uv run --frozen python scripts/security_check.py`，通过 OSV 联网查询锁内公共包名和版本，不外发仓库内容；网络或查询异常返回非零。它只覆盖常见秘密格式与 OSV 已收录的包版本问题，不承诺发现所有风险。PR 采用自动代码审查和修复复验，不要求指定人工评审者或人工批准；合并和发布仍需单独授权。

结构校验与人工场景走查不能替代真实模型选择、出图和宿主验收。当前验证状态及交付边界见 [验证记录](docs/VALIDATION.md)。遵守项目约定，Git 提交、推送、PR、合并与发布须取得对应授权。
