# 🎯 IntentRadar · 公开社区竞品替换信号核验与销售赋能引擎 (v3.1 Production Pilot Edition)

> **核心定位**：帮助**具备企业版和迁移承接能力的挑战者软件团队**，发现并核验公开技术社区（Hacker News、GitHub Issues、Dev.to、Google News RSS、V2EX）中的竞品替换需求，交付**有原文证据、匹配产品能力边界、可采取下一步行动**的销售机会。

---

## 🔍 一、 四步连续资格核验体系（Sequential 4-Stage Qualification）

公开社区讨论转化为真实销售机会，必须按顺序通过 **4 个连续核验阶段**（排序分仅用于优先级排序，绝不替代资格阶段；客户产品能力未绑定时最高仅达阶段 2/4）：

```
[阶段 1: 抱怨竞品/痛点存在] ──► [阶段 2: 买方正在评估替代] ──► [阶段 3: 卖方产品能力匹配] ──► [阶段 4: 可触达并推进]
```

1. **生产模式与历史基准集严格物理隔离（Dataset & Freshness Isolation）**：
   - 实时生产模式（`python3 main.py`）绝不自动混入 `get_mock_signals()` 历史基准集；当实时采集为空或异常时，如实输出 0 条生产状态报告。
   - 每条信号显式标注 `dataset_kind`（`live_production` / `historical_benchmark`）、`freshness_status` 与 `delivery_eligible`，由工作台、导出与飞书/企微 Webhook 统一执行门控。
2. **完整原文保存与三态证据来源（Full Verbatim Text & Tri-State Provenance）**：
   - 5 类采集器与 10 条 HN 官方 Firebase API 基准样本（含 `hn_38227662` 完整 8 段原文）均 100% 保存未截断的 `raw_content` 与规范化 `content`。
   - 对 **企业/团队规模（`team_scale`）**、**预算状态（`budget_status`）**、**选型决策角色（`decision_authority`）**、**迁移窗口（`migration_urgency`）** 分别标注 `[原文明示]` / `[模型推断]` / `[未知]` 及对应原文依据片段（`evidence`）。
   - 严格区分 **作者原文点名的候选产品（`candidate_alternatives`）** 与 **系统同赛道参考候选（`system_recommended_alternatives`）**。
3. **句法方向性实体抽取与负向/推广帖拦截（Syntactic Directionality & Adversarial Gate）**：
   - 识别 `"Migrating from A to B"` / `"Replacing A with B"` 句法方向，确保 `A` 为被替换竞品、`B` 为迁移目标候选。
   - 自动识别并阻断 **买方明示不替换**（`"NOT looking to replace"` / `"no plans to switch"` -> 阶段 1/4，已阻断）、**厂商自我推广帖**（`"Show HN: We built..."` -> 阶段 0/4，已排除）以及 **无选型决策权抱怨**（`"not my choice"` -> 阶段 1/4，已阻断）。
4. **全链路统一话术门控与同源 BD 手册（Unified Outreach Policy Gate）**：
   - 后端统一输出 `outreach_policy`（`blocked` / `neutral_inquiry_only` / `approved_recommendation`），由前端展示、单条复制、批量复制、CSV/XLSX 导出与 Webhook 推送共同执行。
   - 默认未绑定特定卖方能力档案时，系统仅生成不带任何产品承诺的 **中立资格核验提问**；绑定卖方档案时强制校验非空适配竞品与核准能力（严禁 `*` 通配符或自动补造能力），并按真实发送人身份（研发团队 / 销售顾问 / 选型顾问）披露。
   - 内部 BD 种子客户敲门信 100% 从 `get_mock_signals()` 同一条已核验记录动态生成，默认隔离输出至 `/tmp/intent_radar_internal/internal_bd_ops.html`，且 GitHub Pages 工作流仅打包公开客户端构建目录 `_site`。

---

## 🏗️ 二、 仓库模块与代码结构

```text
intent-radar/
├── main.py                      # CLI 主入口：严格隔离实时生产模式与 --demo 历史基准模式
├── config.json                  # 采集源查询词、并发超时、评分阈值与 Webhook 配置
├── test_suite.py                # 自动化对抗与生产试点验收测试套件（覆盖 8 大类反例与门控测试）
├── report.html                  # 客户交付端：公开社区竞品替换信号核验工作台（预编译 CSS，零内部 BD 数据）
└── engine/
    ├── state_store.py           # SQLite 跨轮次状态存储：按 (source, source_id) 去重、计算 content_hash 追踪版本更新与客户推送记录
    ├── collector.py             # 5源并发采集器（HN/GitHub/Dev.to/Google News RSS/V2EX，支持 HTTP-date Retry-After、源冷却与非阻塞超时）
    ├── analyzer.py              # 四步连续资格判研引擎（句法方向抽取、反例阻断、System/User 提示隔离、JSON Schema 校验与话术门控）
    ├── dispatcher.py            # 交付与推送门控器（生成 report.html、隔离输出内部 BD 手册、执行 Webhook 资格与版本门控）
    ├── frontend_assets.py       # 前端交互与导出引擎（会话内存权威回退、无障碍焦点恢复、CSV 公式转义与 OpenPyXL 零警告 XLSX 生成）
    ├── compiled_css.py          # 预编译生产级 Tailwind CSS v3.4.17 样式表
    ├── growth_playbook.py       # 卖方能力档案预设（含真实发送人角色）与同源动态生成的内部试点方案定义
    └── mock_data.py             # 10 条经 Hacker News 官方 Firebase API 逐字核验的历史基准样本集
```

---

## 🚀 三、 快速运行与验收测试

```bash
# 1. 运行自动化生产试点与反例测试套件
python3 test_suite.py -v

# 2. 生成历史基准核验工作台 (report.html)
python3 main.py --demo
```
