# 电商详情页 Skill 使用手册

本手册对应正式发行 **v0.1.1**，来源提交为 `d2d84ba0c85d21967306ee5ae8ada4475fdaf489`。从 [GitHub Release](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/releases/tag/v0.1.1) 获取完整交付。手册在发行后追加，文档提交会比发行提交新；不会因此改写该标签或附件。

| 角色 | 需要做什么 |
|---|---|
| 普通成员 | 下载四个附件 → 校验 → 安装完整 Skill → 确认 Host 来源 → 提供自己的商品资料并调用。无需克隆源码、安装 Python／uv 或部署 MCP Server。 |
| 开发者／维护者 | 阅读仓库规范、准备锁定开发环境、修改和评测，经 PR、必需 CI 与评审后交付。见本手册最后两节。 |
| 绘图服务维护者 | 仅在成员需要生成图片且 Host 尚无相应能力时，按实际服务单独配置；不属于安装这个纯指令 Skill 的必要步骤。 |

已验证组合：Windows、Codex CLI **0.163.0**、本地 PowerShell **7.6.5**，模型评测使用 CLI 默认 `gpt-6.1-sol` 和本地绘图替身。以下命令使用 PowerShell 7.4 或更新版本；其他版本的具体组合未逐一认证。Claude Code、DSH、Codex Desktop 原生交互、真实绘图供应商、商业视觉质量及成员生产环境尚未验收。

旧发行 [v0.1.0](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/releases/tag/v0.1.0) 及其[固定旧版手册](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/blob/f024fd901739067e67f10f344f7512abd91ecf4d/MANUAL.md) 保留。旧版使用 reference/ 与 assets/，本版改为 references/ 与 templates/，业务规则和模板内容不变。

已有旧版目录时先核验和备份，再用**旧版自己的工具与可信清单**卸载，不能让新版工具直接覆盖或重命名旧副本。新旧下载目录分开放，每次切换版本重开 PowerShell 并完整执行对应 VERIFY，不沿用上一版本的 `$Verified`。有本地定制或额外文件时停止自动卸载，保留并交维护者迁移。

## 1. 普通成员：下载正式交付

在 Release 页的 **Assets** 下载下列四个附件，放进同一个独立目录。`Source code (zip/tar.gz)` 是开发源码，普通成员使用表中专用 ZIP。

| 附件 | 用途 |
|---|---|
| `ecommerce-detailpage-creator-v0.1.1.zip` | 一个完整的四文件 Skill |
| `manifest.json` | 版本、完整提交、ZIP 摘要和四文件清单 |
| `SHA256SUMS.txt` | ZIP、manifest、安装工具的摘要清单 |
| `Manage-Skill.ps1` | 本地校验、拒绝覆盖安装、漂移检查、受限卸载 |

也可在 PowerShell 中**整块执行**下面的下载步骤。目录已存在时会停止，保留已有文件；浏览器已下载的成员跳过本块，在后面的校验块把 `$DeliveryDir` 改成实际目录即可。网络失败留下的目录不能当作完整下载，换一个空目录重新取得四附件。

```powershell
$ErrorActionPreference = 'Stop'
$Verified = $null
$DeliveryDir = Join-Path $env:USERPROFILE 'Downloads/detailpage-v0.1.1'
if (Test-Path -LiteralPath $DeliveryDir) { throw '下载目录已存在；保留现有文件，选择新的空目录或直接校验完整下载。' }
New-Item -ItemType Directory -Path $DeliveryDir -ErrorAction Stop | Out-Null
$ReleaseBase = 'https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/releases/download/v0.1.1'
foreach ($name in @('ecommerce-detailpage-creator-v0.1.1.zip', 'manifest.json', 'SHA256SUMS.txt', 'Manage-Skill.ps1')) {
    Invoke-WebRequest -Uri "$ReleaseBase/$name" -OutFile (Join-Path $DeliveryDir $name) -ErrorAction Stop
}
Write-Host '四个附件已下载；尚未完成可信摘要校验。'
```

交付目录示例：

```text
Downloads/detailpage-v0.1.1/
├── ecommerce-detailpage-creator-v0.1.1.zip
├── manifest.json
├── SHA256SUMS.txt
└── Manage-Skill.ps1
```

## 2. 校验四附件，再安装

下面摘要来自本次正式 Release，不能通过“计算下载文件自己的摘要再填回去”证明下载可信。未来版本须从对应的可信发行记录取得**新版本**摘要，不能沿用本表。

| 文件 | SHA256（64 位十六进制） |
|---|---|
| ZIP | `fef9bc28046d14817edc495b0f635080068a7070172116b838c179d725afe41a` |
| manifest.json | `1251a192c4c1ae9238db4906e81d220628eaf0d071ec1bc5af990d96ead38859` |
| Manage-Skill.ps1 | `5b8744aa7029f2ff6f83dd0a7e77ae979cc07b0ad79dc4e97bd01dfc00e60bb2` |
| SHA256SUMS.txt | `0678183dc9df134044c8ce5308867696a4cf96d35a3b9f9612088297423ca6ea` |

**VERIFY 整块执行**。它先清除旧的成功状态，校验四附件后才运行安装工具的只读 Verify。任一失败都不会留下可供后续安装使用的成功状态。新开 PowerShell 窗口后须重做本块。

```powershell
$ErrorActionPreference = 'Stop'
$Verified = $null
try {
    if ($PSVersionTable.PSVersion -lt [version]'7.4') { throw '请使用 PowerShell 7.4 或更新版本。' }
    $DeliveryDir = Join-Path $env:USERPROFILE 'Downloads/detailpage-v0.1.1'
    $Expected = @{
        'ecommerce-detailpage-creator-v0.1.1.zip' = 'fef9bc28046d14817edc495b0f635080068a7070172116b838c179d725afe41a'
        'manifest.json' = '1251a192c4c1ae9238db4906e81d220628eaf0d071ec1bc5af990d96ead38859'
        'Manage-Skill.ps1' = '5b8744aa7029f2ff6f83dd0a7e77ae979cc07b0ad79dc4e97bd01dfc00e60bb2'
        'SHA256SUMS.txt' = '0678183dc9df134044c8ce5308867696a4cf96d35a3b9f9612088297423ca6ea'
    }
    foreach ($name in $Expected.Keys) {
        $path = Join-Path $DeliveryDir $name
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { throw "缺少附件：$name" }
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Expected[$name]) { throw "摘要不符：$name" }
    }
    $result = & (Join-Path $DeliveryDir 'Manage-Skill.ps1') -Action Verify -BundleDir $DeliveryDir -ExpectedManifestSha256 $Expected['manifest.json'] | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or !$result.passed) { throw '包结构或内容核验失败。' }
    $Verified = [pscustomobject]@{ Dir=$DeliveryDir; ManifestSha=$Expected['manifest.json']; ScriptSha=$Expected['Manage-Skill.ps1']; Version='v0.1.1'; Commit='d2d84ba0c85d21967306ee5ae8ada4475fdaf489' }
    Write-Host '四附件及 Skill 包校验通过；尚未安装。'
} catch {
    $Verified = $null
    throw
}
```

默认采用已实测的**项目级安装**：选择你实际工作的业务目录，安装到 `<业务目录>/.agents/skills/`，从该目录启动 Codex。下面会让你输入一个已经存在的业务目录完整路径（直接粘贴路径，不加外层引号）；不要选开发此 Skill 的源码仓库，以免与开发副本重名。

**INSTALL 整块执行**，只在本次 VERIFY 成功后运行。安装前再次核对脚本，工具还会重新核对 manifest、ZIP 与每个文件。已有同名技能一律拒绝覆盖；先比较版本和定制，不能直接清空旧目录。

```powershell
$ErrorActionPreference = 'Stop'
try {
    if (!$Verified) { throw '请先在当前窗口完整执行 VERIFY。' }
    $Manager = Join-Path $Verified.Dir 'Manage-Skill.ps1'
    if ((Get-FileHash -LiteralPath $Manager -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Verified.ScriptSha) { throw '校验后安装工具已变化。' }
    $SkillProjectDir = [IO.Path]::GetFullPath((Read-Host '请输入已经存在的业务目录完整路径'))
    if (!(Test-Path -LiteralPath $SkillProjectDir -PathType Container)) { throw '业务目录不存在。' }
    $TargetSkillsDir = Join-Path $SkillProjectDir '.agents/skills'
    New-Item -ItemType Directory -Path $TargetSkillsDir -Force -ErrorAction Stop | Out-Null
    $installed = & $Manager -Action Install -BundleDir $Verified.Dir -ExpectedManifestSha256 $Verified.ManifestSha -SkillsDir $TargetSkillsDir | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or !$installed.passed) { throw '安装失败；检查诊断和可能保留的部分安装，不重复覆盖。' }
    $checked = & $Manager -Action Check -BundleDir $Verified.Dir -ExpectedManifestSha256 $Verified.ManifestSha -SkillsDir $TargetSkillsDir | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or !$checked.passed) { throw '安装后文件核验失败。' }
    Write-Host "安装文件核验通过：$($Verified.Version) / $($Verified.Commit)；请继续核对 Host 发现与调用。"
} catch {
    $Verified = $null
    throw
}
```

实际安装形态：

```text
<你选择的业务目录>/.agents/skills/
└── ecommerce-detailpage-creator/
    ├── SKILL.md
    ├── references/
    │   ├── workflow.md
    │   └── deliverables.md
    └── templates/
        └── design-record-template.md
```

技能父目录、技能根目录、下载目录是三个不同位置。不要把 ZIP 原样丢进技能父目录，不要多套一层同名文件夹，不要只复制 SKILL.md。换一个业务目录需显式选择新的目标，重新安装并确认来源；不要同时安装多个同名副本后猜测哪个生效。

可选用户级目录按 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills) 为 `~/.agents/skills/`，供同一运行用户跨项目使用；Windows 通常对应 `$env:USERPROFILE/.agents/skills/`。本次未操作真实用户级安装位置，伪用户目录隔离探测未发现目标，故**用户级 Host 发现仍未验收**，不以项目级成功替代。若确需用户级使用，先核对 Host 实际主目录和有效来源再单独验收。`~` 是运行 Host 的主目录，本机路径不能直接用于 WSL、容器、SSH 或云端。

## 3. 确认 Host 发现，再开始任务

关闭旧会话，从 INSTALL 时选择的业务目录重新启动已安装的 Codex CLI。核对技能列表中有 `ecommerce-detailpage-creator`，来源是刚才安装的技能根。若界面未展示来源，可要求实际读取入口并查看文件读取轨迹；只看到名称或模型说“已使用”不能单独证明来源和正文已加载。同名冲突先记录所有路径，不删除其他技能。

显式调用示例（把附件换成自己的真实商品资料）：

```text
$ecommerce-detailpage-creator
请实际读取该技能入口。附件是本商品实图及已确认参数，先给事实表、买家顾虑映射和六屏方案。
本次只策划，不生成；尺寸和屏数证据不足时请指出待补项，不移用教程参数。
```

自然语言正例：“根据这些真实商品图和已确认资料策划六屏详情页，先给方案，不生成。”预期有来源编号、事实、顾虑、逐屏文案／画面依据、待确认项及准确阶段状态。资料不足以支撑六屏时，应缩减或标记待补，不凑数。

近邻反例：“只把这一张商品主图换成白底。”预期转向已有单图编辑能力，不执行整套多屏详情页流程。信息不足例：“没提供商品图，直接写 6L 和健康少油。”预期指出无依据，给问题清单和有边界的草案，不虚构事实或生图。

Skill 是指令方法，不自带绘图服务。策划和提示词无需密钥；成品生成需要 Host 已提供的真实看图、生成／编辑与保存工具。先核对实际工具标识、schema、模型、参考图用途和授权。方案确认后才允许提交；只同意策划不等于同意收费生成。结果未知先查询原任务，不能盲目重提或换任务 ID。模型／供应商可能收费，本次安装检查不调用真实绘图。

安装检查完成的证据应分别记录：文件与摘要匹配、Host 正确来源可见、显式／隐式选用、必要资源读取、实际产物与失败反馈。`Manage-Skill.ps1` 的 `host_verified=false` 是准确边界，文件核验不能代替宿主业务验收。

## 4. 怎样填写摘要和商品资料

**安装／交付摘要**记录下面这些具体值，不填 `latest`、七位短 SHA 或本机猜测的版本。SHA256 是 64 位摘要；完整 Git 提交是 40 位标识，两者不能互换。

```text
Skill：ecommerce-detailpage-creator
发行：v0.1.1
来源提交：d2d84ba0c85d21967306ee5ae8ada4475fdaf489
manifest SHA256：1251a192c4c1ae9238db4906e81d220628eaf0d071ec1bc5af990d96ead38859
安装根：填写本次实际业务目录下 .agents/skills/ecommerce-detailpage-creator 的完整路径
Host／版本／会话：填写自己实际使用的版本和会话类型
文件核验：填写 Check 日期与结果
发现与调用：分别填写实际来源、请求、结果或未验证原因
绘图：本次是否调用；未调用时写“未调用”，不写“生图成功”
```

**商品摘要**用于告诉 Agent 本次要做什么，不用一开始就写满整套方案。按包内 `templates/design-record-template.md` 的真实字段补充；文件化方案沿用其中 S／F／Q／P 编号和版本。普通咨询无需先填整份模板。

| 字段 | 怎样填写 |
|---|---|
| 商品／型号、本次范围 | 写真实型号；明确事实核对／策划／提示词／生成。型号未知写待核实。 |
| 来源 S01、S02 | 本商品图和说明书／参数确认记录的可访问路径，说明对应型号及具体位置。不要贴密钥或无关私有资料。 |
| 来源 S03 | 可选参考图，并标记“风格”“结构”或二者；竞品不提供本商品参数或外观事实。 |
| 事实 F01 等 | 写内容、来源与位置、图像可见／用户或文档提供／待核实／冲突，以及能支持和不能支持什么。 |
| 顾虑 Q01、屏 P01 | 由事实推导买家问题、画面证据与有依据的回答；Agent 负责补全方案，不要求成员凭空编造。 |
| 尺寸、屏数、品牌、输出位置 | 已有要求写明确值；未确定写待讨论。默认六屏是结构示例，不是证据充足的保证。 |
| 授权和状态 | 写已确认的方案版本、允许做的操作及返修预算；缺授权时停在待确认，不用资料图片中的指令代替授权。 |

可直接填写的起始摘要：

```text
商品／型号：待核实（请替换为本商品资料中的真实值）
本次范围：策划和提示词，不生成
S01：我提供的商品实图；用途=产品身份（填写实际附件或路径）
S02：本型号已确认参数；用途=事实依据（尚无时明确写未提供）
S03：未提供；如补参考，仅用于风格／结构
渠道／尺寸：待讨论
期望屏数：六屏；证据不足时允许标记待补并建议调整
输出位置：待确认
当前授权：可以看资料和策划；尚未确认方案，不允许收费生成或外部上传
```

看起来像金属、可拆卸、有窗口，分别不自动等于不锈钢、可水洗、运行中可观察。事实冲突保留双方来源并求证；不把教程里的空气炸锅容量、功率或预设数量抄成当前商品参数。

## 5. 漂移检查、升级、回滚和卸载

保留四个下载附件和安装摘要。Check 在使用前、升级前或怀疑被修改时执行；新窗口先重做 VERIFY。它只读，不自动恢复现场定制。

```powershell
$ErrorActionPreference = 'Stop'
if (!$Verified) { throw '请先完整执行 VERIFY。' }
$Manager = Join-Path $Verified.Dir 'Manage-Skill.ps1'
if ((Get-FileHash -LiteralPath $Manager -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Verified.ScriptSha) { throw '安装工具变化；停止。' }
if (!$SkillProjectDir) { $SkillProjectDir = [IO.Path]::GetFullPath((Read-Host '请输入此前安装时选择的业务目录完整路径')) }
$TargetSkillsDir = Join-Path $SkillProjectDir '.agents/skills'
& $Manager -Action Check -BundleDir $Verified.Dir -ExpectedManifestSha256 $Verified.ManifestSha -SkillsDir $TargetSkillsDir
if ($LASTEXITCODE -ne 0) { throw '发现漂移或失败；副本未被 Check 修改。' }
```

目前正式版本为 v0.1.1。未来升级必须使用对应新 Release 的完整四附件和新可信摘要，不能跟随 main 自动覆盖。先记录现用版本、停止使用／编辑该副本，检查定制并备份完整旧包到技能扫描目录之外；检查点未通过时保留原副本并停下。没有可信旧清单的历史手工副本不要套用新清单强制卸载，应先交维护者核对迁移。

无定制且旧包核验通过时，可用**旧版本**匹配的工具和 manifest 卸载，再安装新版本并重新发现／验收。需要回滚时，保留新版本失败证据，恢复完整已验证旧包及其匹配记录，再核对 Host 来源和代表性任务；不能只退一个 SKILL.md。存在定制／额外文件时自动卸载拒绝执行，先保存并交维护者安排迁移。生产跨版本升级尚未实测，隔离检查覆盖的是安装、同包恢复、漂移和保留行为。

卸载只针对本技能。关闭正在使用它的会话、停止编辑，完整 VERIFY 后整块执行：

```powershell
$ErrorActionPreference = 'Stop'
if (!$Verified) { throw '请先完整执行 VERIFY。' }
$Manager = Join-Path $Verified.Dir 'Manage-Skill.ps1'
if ((Get-FileHash -LiteralPath $Manager -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Verified.ScriptSha) { throw '安装工具变化；停止。' }
if (!$SkillProjectDir) { $SkillProjectDir = [IO.Path]::GetFullPath((Read-Host '请输入此前安装时选择的业务目录完整路径')) }
$TargetSkillsDir = Join-Path $SkillProjectDir '.agents/skills'
& $Manager -Action Uninstall -BundleDir $Verified.Dir -ExpectedManifestSha256 $Verified.ManifestSha -SkillsDir $TargetSkillsDir
if ($LASTEXITCODE -ne 0) { throw '卸载失败或部分卸载；保留残留用户内容，先检查诊断，不递归清空目录。' }
Write-Host '本技能已卸载；重开会话核对该来源不再可见。'
```

工具先核对完整四文件；漂移或额外目录会阻止删除。核验后若并发出现新内容，只删除清单内文件、非递归删除空目录，新增内容保留并返回失败，可能已部分卸载。它不承诺事务回滚；其他技能、宿主配置、业务素材和任务不应被删除。卸载后仍可见同名技能时查来源，不清空所有技能目录。

| 现象 | 处理 |
|---|---|
| 摘要不符、缺附件或 ZIP 失败 | 停止；核对正式版本、四文件与可信摘要，保留现有目录，在新空目录重新下载。不要把计算出的未知摘要填成可信值。 |
| 目标目录已存在 | 这是拒绝覆盖；比较版本、定制和来源，按升级流程处理。不要直接删目录重试。 |
| 脚本被执行策略或权限阻断 | 遵守组织策略与管理员流程；不全局修改策略、不用其他工具绕过拒绝。仅文件摘要通过不代表已安装。 |
| 未发现／同名来源错误 | 核对 Host 实际运行用户、安装父目录、重开会话和真实路径；Windows、WSL、远端目录分别确认。 |
| Check 报漂移 | 保留副本与差异，向维护者反馈；不要自动恢复用户定制。 |
| 工具不可用、任务结果未知 | 交付能完成的策划／提示词及准确状态；查询原标识，不重提交可能收费任务。 |
| 输出不合格 | 按事实、顾虑、方案、渲染定位；按授权和纠错预算返修，不能把提示词或局部成功称为整套已验收。 |

## 6. 开发者：源码与评测

源码为 [ecommercial-detailpage-creator-skill](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill)。先读 [AGENTS.md](AGENTS.md)、[CONVENTIONS.md](CONVENTIONS.md)、[工程指南](docs/ENGINEERING-GUIDE.md)和[手册规范](docs/MANUAL-WRITING-GUIDE.md)。开发目录中的 `.agents/skills/` 是实验来源，正式成员副本从固定发行包取得。

在独立源码检出根准备锁定环境：

```powershell
uv sync --locked --group dev --python 3.12
if ($LASTEXITCODE -ne 0) { throw '锁定环境准备失败。' }
uv run --frozen python scripts/ci_check.py
if ($LASTEXITCODE -ne 0) { throw '本地检查失败。' }
```

开发工具 uv 0.12.9，Python 3.12 或更新；开发依赖 PyYAML 6.0.3、Pillow 13.0.0 由 `uv.lock` 固定，不是业务运行依赖。共用检查覆盖结构／文档、62 项测试、证据一致性、常见秘密和公共锁定包 OSV 风险；OSV 只接收公共包名版本，网络异常阻断，不能记成零漏洞。每子检查最多 120 秒；JSON 汇总和日志在 `.eval-runs/ci/`，成功 0、失败 1。

真实 CLI 的发现诊断、模型评测、判分与归档命令见 [EVAL-HARNESS](docs/EVAL-HARNESS.md)及 [OPERATIONS](docs/OPERATIONS.md)。模型评测需要已授权的 CLI 认证和额度，会消耗模型用量；绘图替身无网络、无收费图像调用。保持固定场景和重复次数，正文变化按影响重跑，不能只挑一次成功；公共证据门禁不是模型重放。

## 7. 开发者：审核、发行与反馈

流程为分支 → PR → Windows `repository-checks` 与 `automated-review` → 合并提交复验 → dev 快进与该分支 push CI → 受控 CD。现有规则不要求指定人工评审者，仍须实际 Agent 评审，不绕过检查或覆盖正式版本。

维护者获授权后，选取未使用的新版本和完整审核 SHA，在 main 上手动触发 `release.yml`。入口核对 main/dev 精确提交、各自最新成功 push CI 和自动评审，拒绝已有标签／Release；从 Git 对象构建白名单包、验证安装／核验／卸载，并原子创建固定 SHA 标签，只生成预发布草稿。自审及资产／安装／Host 验证通过后，再显式转为正式 Release。失败先查固定 Release ID、标签和状态，不重复上传或改写已发布附件。

本次发行证据见 [交付记录](docs/DELIVERY.md)和 [规范适配评测](docs/STANDARDS-ALIGNMENT.md)。发布后文档通过后续 PR 补充，发行标签仍固定 `d2d84ba0c85d21967306ee5ae8ada4475fdaf489`。本项目没有 tag push CI；不要把 main CI 或草稿 CD 称为标签 CI。成员正式环境未被集中同步，发布不代表所有人已安装。

反馈请关联发行版本、完整 SHA、Host／模型／OS、脱敏请求、输入来源、实际结果与错误，说明是否发生外发或收费及现有任务 ID。私有商品资料、原始会话和秘密不直接放进公开 issue。可共享改进经分支／PR 回流，成员不长期维护无版本的独立副本。
