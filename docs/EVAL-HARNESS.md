# 实际选择与行为评测

本项目使用固定的 16 个场景和 [量规](../evals/RUBRIC.md)。执行方法参考 [OpenAI 官方 Skill 评测说明](https://developers.openai.com/blog/eval-skills)：记录实际工具轨迹和产物，使用独立模型会话评分，避免只核对最终文字。

## 准备与运行

在仓库根使用 uv 准备锁定开发依赖，保留现有用户配置：

```powershell
uv sync --locked --group dev
uv run --frozen python scripts/check.py
uv run --frozen python -m unittest discover -s tests -v
```

实际模型执行需要本机已安装且已登录的 Codex CLI；不会安装 CLI、请求新 API Key 或打印凭据。合成图片用 Pillow 软件绘制，需要 Windows 的 `C:/Windows/Fonts/msyh.ttc`（微软雅黑）用于中文；字体不随技能分发。没有这个字体时准备阶段会失败，不能算 Skill 失败或悄悄使用不可读文字。

先独立测只看目录的选择，再测加载后的任务行为，每次使用新的证据目录，每层每例 3 次：

```powershell
uv run --frozen python scripts/run_selection_eval.py --output .eval-runs/my-selection --workers 4
uv run --frozen python scripts/run_behavior_eval.py --output .eval-runs/my-run --workers 3 --timeout 300
uv run --frozen python scripts/grade_behavior_eval.py --run .eval-runs/my-run --workers 3
```

补测显式调用或局部回归可使用 `--cases B07 --mode explicit --repeats 3`，与完整集分开报告。默认 `--discovery catalog` 提供目录并关闭原生发现；`--discovery native` 在每条试验的独立 Git 项目中放入冻结完整技能包，开启原生发现，不向请求人工拼入目录。先使用 `probe_host.py` 验证实际元数据，再运行 native 的正例／近邻及显式请求。native 显式请求另要求实际读正文，避免将缺少读取轨迹当成已验证注入。

执行器参数：`--output` 必填且为全新 `.eval-runs/` 子目录；`--cases` 默认 all，否则为固定 ID 的逗号列表；`--repeats` 正整数、默认 3；`--workers` 1–4、默认 3；`--timeout` 每条模型进程的秒数、必须大于零、默认 240；`--mode` 为 implicit／explicit。未知参数或非法组合在创建工作区前以 2 退出，不覆盖旧目录；UTF-8 JSONL 逐条输出状态，文件产物供评分取数。0 只表示模型任务都结束，不代表行为通过，非零表示基础设施或参数失败；断流或超时保留部分文件，不自动重提生成。

评分器 `--tag grades-v2` 可在同一原始试验上新建一轮评分，保留旧判断；用于修复可证实的评分错误。评分预期不可为了使模型过关而放宽；被测模型不接收 `expected`、`critical` 或 `expected_selection`。修改技能后另建完整试验目录，记录全包摘要，不用旧快照的成功拼凑为新版本全量通过。

恢复评分时，源码必须与该 tag 内冻结的 `grader.py` 完全一致；变更评分器后必须新建 tag，不能给旧结果重新标注当前源码摘要。汇总按完整 trial ID 集合检查，拒绝重复、额外 ID 和相互矛盾的通过标记；未完成三次的批次不能算完整。

每个 tag 同时只运行一个评分器进程（内部可使用 `--workers`）。每次裁判调用保存在 `<tag>/<case>/attempt-NNN/`，失败与中断尝试保留；仅原子写入并通过完整性检查的 `results.json` 才表示该组完成。同 tag 恢复会重试没有完整结果的组，已完成的行为失败样本不会为提高分数而重跑；汇总账本从各组结果重新构建，避免中断后追加重复记录。旧历史批次保留旧目录布局。

## 隔离与模拟边界

- 新建 CLI 会话，忽略用户 CLI 配置，禁用插件、Hooks、真实生图、浏览器、Shell、记忆、多 Agent 和技能自动安装；仅注册 `eval_lab` 本地 stdio MCP。
- 模型保持 CLI 默认选型，执行器不传模型覆盖参数。实际版本、模型和禁用开关保存在 `run.json`、每条 `trial.json` 及命令记录中。catalog 模式关闭原生发现，不冒充宿主验收；native 模式验证实际 CLI 发现，仍不能推断 Desktop、其他版本或其他宿主兼容。
- 隐式选择时给目标及两个相邻能力的名称／描述，轮换目录顺序，由模型决定选用、拒用或澄清。适用后实际读取技能和按需资料。显式补测单独告知技能名称。
- 独立选择执行器只给目录、当前请求及 `selection_context` 原始历史，不暴露正文或 MCP。继续任务需保留其方案类别；用例 1.1 补齐参数屏、清洗屏、文案修改、已确认六屏及素材归档的历史用途。没有增加 expected 或评分答案到模型输入。模型输出的技能 ID 与固定 oracle 严格比较。
- 行为执行器保留实际资料读取和工具执行；其 JSON 自报 `selection` 可能把“需要补资料”写成 clarify，所以该字段单列诊断。真实技能适用性另由独立选择层验证，行为层仍逐项检查原 expected、critical、任务保存、看图和权限边界，没有将格式标签当作任务成功。
- 替身不导入 HTTP 客户端、供应商 SDK 或凭据模块，不调用外部命令。所有输入均为合成资料，读写限制在本次试验工作区；技能资料只读且限制在冻结技能根。`upload_external` 是无网络陷阱，仅记录企图，不能真的上传。
- `inspect_images` 真正返回 MCP PNG 图像块，记录尺寸和 SHA256。文件路径或历史描述不代替看图。结果刻意可能缺少演示证据，B11 编辑结果故意保留可见乱码，用于验证诚实验收，而非证明商业绘图质量。
- 绘图操作需要实际提交、原任务查询及保存；原 P03 首次查询仍在运行，禁止重提。归档必须实际复制并写清单，保留源文件和旧版本。
- 独立裁判接收真实回复、调用参数、图像块送达记录、确定性夹具视觉对照和逐项量规；大段技能正文及二进制不复制到裁判输入。确定性判定检查未经批准的提交、原任务重提、缺保存／看图和外发尝试。授权局部编辑不等同于重复初次生成。
- 范围外任务额外读取候选技能边界时保留诊断，不把只读本身等同于套用多屏流程；原量规判定的是正确转向及不执行整套详情页。合法单图局部返修可以使用已授权原图派生且已保存的编辑结果，评分器按真实文件与任务链核对，不要求每次必须回到原图，也不接受任意其他图片。

模型推理仍需要连接 Codex 服务并消耗已有额度；“离线”仅指绘图替身无网络，不声称整个模型评测无网络或无推理成本。未连接真实图像供应商，模拟不替代真实服务、中文质量、用户视觉验收及跨宿主验证。

## 证据与复核

每个批次保留 `run.json`、`skill-manifest.json`、冻结的 `skill/` 和 `harness/`；每条试验保留输入、种子、原始输出、`answer.json`、`trial.json`、`calls.jsonl`、合成图片及本地记录。评分目录保留评分器源码快照、裁判输入和原始判定，汇总见 `summary-grades.json`。

独立选择批次不创建模拟图片或 MCP 轨迹，保留冻结的技能、场景和执行器、实际输入／输出及 `summary.json`。冻结技能只用于来源追溯，模型没有读取它的工具。描述不变而正文修复时，选择结果只用于同一描述，正文行为仍单独复验。

原始结果均在 `.eval-runs/`，不入 Git；源码、锁、量规及安全合成夹具生成器保留在仓库。最终可分享的脱敏结论见 [验证记录](VALIDATION.md)，不要把未完成评分或单次成功称为三次通过。

`evals/evidence.json` schema 2 是维护者从原始批次审计导出的脱敏记录，保留逐次 ID、判定项、版本指纹、原始文件摘要、实际资源读取和时延统计，不含原回复、图片、客户资料或本机路径。旧 schema 1 原样保留为 `evals/baseline-evidence.json`，不把旧正文结果标成新版本。CI 用 `uv run --frozen python scripts/audit_evidence.py` 核对完整性和当前版本；它是一致性门禁，不是模型重放、独立签名或商业质量背书。

导出时须明确指定六个完整批次：`--selection`、`--behavior`、`--explicit`、`--native-implicit`、`--native-negative`、`--native-explicit`，以及实际评分 `--grade-tag`（默认 grades）。参数均指向 `.eval-runs/` 内已有目录。只看描述的选择证据允许在描述和用例完全不变时复用，冻结选择执行器及命令版本仍原样追溯；新正文、资源和 mock 行为必须使用匹配的新快照。导出须核对批次 mode／discovery、冻结执行器、各试验命令与显式提示，拒绝将 catalog 试验贴为原生／显式。最终原生三组已用仓库执行器的 native 模式重新运行，早期手动执行器轨迹仅留作诊断。导出先重算机械检查、核对裁判原判、完整 ID 和逐项标准，以及 B11 两轮返修和逐任务三次查询预算，再覆盖公共摘要；不得为凑通过数手改结果。

## 对比、归档与清理

比较同一固定集、重复次数、CLI／默认模型和模拟资料；原生补测另对照本轮迁移前基线。报告应触发正确数／分母、近邻误触发数／分母、任务通过／分母及关键违规，超时与失败不从分母消失。时延记录每条 CLI 启动至最终响应的秒数、中位数和经验 P95；运行时间、并发与缓存不同，不能当作严格性能因果结论。文本 CLI 记录没有已核实的输入／输出／缓存 token 分类，标未知，不凭文件字节数声称 token 节省。

所有新测试临时目录位于工作区 `.eval-runs/tmp/`，由 `TemporaryDirectory` 和 unittest cleanup／finally 清理；原生发现的临时 Home 同样位于本次证据目录并清理，不修改用户 Home。模型输出、失败轨迹和 PNG 先保留以便审计，全部相关进程结束后执行：

```powershell
uv run --frozen python scripts/archive_evidence.py --run .eval-runs/my-closed-batch --output .eval-runs/my-closed-batch.zip
uv run --frozen python scripts/archive_evidence.py --verify --output .eval-runs/my-closed-batch.zip
```

归档须使用新路径，输入和输出均限制在 `.eval-runs/`，输出不能位于输入内部；排除 `.git`、`.venv` 和 `__pycache__`，拒绝链接资源，写后逐成员核对 SHA256／大小，并重读源清单确认没有并发写入。stdout 为一个 JSON，成功 0、失败 1、参数错误 2；归档工具本身**不删除源目录**，失败时保留源及已有已验证归档。调用者在已验证归档后，仅清理本次拥有且路径已核对的临时工作区；旧评测、用户环境和原图不清理。

公共评测证据留在 `evals/`，完整原始轨迹仅作本地忽略 ZIP。需要重审原始轨迹时，先用归档清单核验摘要，在工作区独立临时目录恢复，再按实际恢复路径传给导出器；结束后清理本次恢复目录。CI 只上传 `.eval-runs/ci/` 的确定性日志，保留 7 天，不上传模型原始轨迹、原图、用户配置或凭据。
