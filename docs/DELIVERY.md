# v0.1.0 交付记录（2026-10-24）

正式发行：[v0.1.0](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/releases/tag/v0.1.0)，Release ID `422621877`，2026-10-24 09:00:18 UTC 发布，`draft=false`、`prerelease=false`。标签和 manifest 的完整来源 SHA 均为 `533262ff2955702e1a646ed9d0b9df58dcfd5f1f`。成员步骤和四附件可信摘要见 [MANUAL](../MANUAL.md)。

## 审核与流水线

| 阶段 | 精确提交及结果 |
|---|---|
| [规范适配 PR #2](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/pull/2) | HEAD `d7fcf42427cf389eb5d69d5fb152ab253afbecbb`；[Windows CI](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/actions/runs/40079011533) 57 项通过，Agent 评审完成 |
| PR #2 合入 | `49687a83058a4a304cc3286d212e8498e4ba7e3e`；[main](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/actions/runs/40079093114) 与 [dev](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/actions/runs/40079170541) push CI 通过 |
| [卸载保留修复 PR #3](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/pull/3) | HEAD `c0a65b7f99786c01bfabb42014dba431158f632a`；[Windows CI](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/actions/runs/40079773495) 58 项通过，Agent 复审无未解决项 |
| 正式发行来源 | PR #3 合入 `533262ff2955702e1a646ed9d0b9df58dcfd5f1f`；[main](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/actions/runs/40079894777) 与 [dev](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/actions/runs/40079963055) 各自 push CI 58 项通过，本地 main/dev 与远端快进一致 |
| 受控草稿 CD | [工作流 40080077506](https://github.com/tsyecommercialdesigner-cloud/ecommercial-detailpage-creator-skill/actions/runs/40080077506) 从上述固定 SHA 成功构建，校验、安装、Check、卸载通过后创建草稿 |

main 强制实际 `repository-checks` 和 `automated-review`，严格基线、管理员受约束、会话需解决、禁止 force push／删除；用户已取消指定人工评审者要求。自动评审评论不伪装成独立人工 APPROVE。合入树与已评审树一致后另做本地和默认分支检查。没有 tag push 工作流，不声称标签 CI。

## 发现、修复与发行自审

最终完整静态审查发现并修复两项 P1：已有同名标签可能使 `--target` 失效，现拒绝冲突并原子创建／核对标签；证据可被贴错 native／explicit 标签，现核对模式、冻结执行器、实际命令与提示，并用当前执行器重跑原生三组。完整行为 48/48，显式生成 3/3，最终原生隐式／近邻／显式各 3/3，关键违规为零；选择元数据未变，复用原 48/48 并明确标注。

首个预发布草稿 ID `422616230` 曾从 `49687a8` 构建。发行自审补充发现递归卸载可能误删核验后新加入的用户文件，故未发布；PR #3 用确定性插入测试证明旧实现失败、新实现保留内容且返回失败，不打印成功。旧草稿和本次创建的未发布候选标签在核对状态与 SHA 后移除，私有下载证据保留；未改写任何已发布版本。

修复后重新构建的正式四附件全部从 GitHub 重新下载，逐项核对 GitHub digest、SHA256SUMS、manifest、ZIP 路径／四文件／大小及来源 Git blob，安装工具也与来源 blob 相同。发布前完成静态自审、58 项本地与远端检查、隔离 Verify／Install／Check／Uninstall／重新安装，且实际 Codex `skills/list` 返回正确安装来源、enabled、无解析错误。

下载包的原生 S01 模拟策划另执行 1 次并独立评分 1/1。修复前后 ZIP 字节完全相同（仅包外安装工具与来源 manifest 等变化），故复用这条相同运行包的语义证据，未冒称再跑一条模型试验。生产成员安装、其他 Host、真实图像供应商、商业视觉效果、用户视觉验收仍未验证。

正式发布后再次重新下载全部四附件并重复摘要、来源核对。MANUAL 的六个 PowerShell 块已提取留证；前五块在隔离成员目录逐块实跑：正式 URL 下载四附件、可信摘要、失败 VERIFY 清空旧状态并阻止安装、拒绝覆盖、Check 保留漂移、额外成员文件阻止卸载、成功卸载／同包重装及无关文件保留均通过。第六块开发环境／共用检查另在源码根实跑。

手册采用用户显式选择业务目录的项目级安装，实际 `skills/list` 发现正确 repo 来源、enabled、无解析错误，按手册卸载后重查目标数量为零。曾尝试以伪用户主目录隔离用户级发现，三次未找到目标；保留失败，未猜根因或改用户真实配置，不计为用户级成功。用户级路径只引用官方文档，具体当前 Host 仍未验收；不将该隔离失败解释成所有真实用户级安装不可用。手册据此不把用户级安装设为默认已验证路径。

## 内容与证据保留

运行包只有 SKILL.md、两份 reference 与一个设计记录 asset。没有 Python 依赖、凭据、真实商品图、原教程七图、模型原始会话或无关源码。发布不代表已同步任何成员正式环境；指定目标前不覆盖本机用户级配置或副本。

公共评测结论在 `evals/evidence.json`，原 schema 1 基线保留；原始评测归档 SHA 见 [规范适配记录](STANDARDS-ALIGNMENT.md)。本轮最终私有证据位于 `.eval-runs/` 的单独归档，CI artifacts 仅确定性日志，保留 7 天；原始轨迹不公开提交。发行后追加文档的 PR 与 CI 单独记录，Git 当前 main/dev 可前进，v0.1.0 标签及资产保持不变。
