# 🎯 IntentRadar · 公开社区竞品替换信号核验与销售赋能引擎 (v3.0 Audit Edition)

> **核心定位**：帮助**具备企业版和迁移承接能力的挑战者软件团队**，发现并核验公开技术社区（Hacker News、GitHub、V2EX、Reddit）中的竞品替换需求，交付**有原文证据、匹配产品能力边界、可采取下一步行动**的销售机会。

---

## 🔍 一、 为什么「抱怨竞品」不等于「可直接成交的采购线索」？

公开社区讨论转化为真实销售机会，必须严格拆分为 **4 个独立核验阶段**（高分不能替代其中任何一步）：

```
[阶段 1: 抱怨竞品] ──► [阶段 2: 正在评估替代] ──► [阶段 3: 卖方产品能力匹配] ──► [阶段 4: 可触达并推进]
```

1. **证据真实性与可追溯性（Evidence Provenance）**：
   - 每条线索强制保存来源唯一主键 `source_id`、原始 URL、原文完整正文、支持关键判断的**原文证据摘录（`evidence_quote`）**、UTC 发布时间（`timestamp`）与采集核验时间（`collected_at`）。
2. **三态资格标注（Tri-State Qualification）**：
   - 对 **企业/团队规模（`team_scale`）**、**预算与付费状态（`budget_status`）**、**选型决策角色（`decision_authority`）**、**迁移窗口与期限（`migration_urgency`）** 分别显式标注：
     - `[原文明示]`：原帖字面直接包含的事实（如 `"we are on the Pro plan"`、`"My startup uses Jira"`）
     - `[模型推断]`：基于上下文角色合理推断
     - `[未知]`：原帖未披露，必须在首轮沟通中核实（严禁将未知脑补为“预算充足”）
   - **负向与边界校准样本**：内置发帖人明示无选型决定权（如 `hn_37146814`: `"Sadly using Jira was not my choice"`）的负向拦截样本，以及单句提问待核验资格样本（如 `hn_36537006`），防止销售团队在无权限抱怨帖上浪费精力。
3. **被替换产品 vs. 候选替代品实体分离**：
   - 严格区分 **被替换标的（`target_competitor`）** 与原帖讨论中提及的 **候选替代方案（`candidate_alternatives`）**。
4. **卖方能力边界门控与诚实利益披露（Capability Gating & Transparent Disclosure）**：
   - **跨赛道不匹配强制拦截**：配置特定卖方产品（如适配 `Jira` 替换的 `Plane`）后，系统仅对同赛道线索生成沟通草稿；对不适配赛道（如 `DocuSign`、`Postman`、`Datadog`）自动阻断推荐。
   - **拒绝伪装“过来人”水军**：所有公开社区回复强制以 `利益相关披露：我参与了 [产品名] 的开发...` 开头，仅引用已核准的产品能力，并主动列出已知限制与待确认项。

---

## 🏗️ 二、 仓库模块与代码结构

本仓库完整公开前后端全部源码与自动化测试套件：

```text
intent-radar/
├── main.py                      # CLI 主入口：支持 --demo 核验样本库模式与实时多源采集模式
├── config.json                  # 采集源查询词、并发超时、评分阈值与 Webhook 配置
├── test_suite.py                # 自动化审计测试套件（校验三态证据、四步资格、防公式注入与双端隔离）
├── report.html                  # 客户交付端：公开社区竞品替换信号核验工作台（无内部BD信息、预编译CSS）
├── internal_bd_ops.html         # 内部运营端：单赛道人工核验试点手册与1对1证据开发信（物理隔离）
└── engine/
    ├── collector.py             # 多源并发采集器（单源超时隔离、指数退避+抖动重试、Retry-After、URL规范化与source_id主键去重）
    ├── analyzer.py              # 四步资格判研引擎（双层预筛、实体分离、Prompt注入边界隔离、三态来源构建与透明披露话术）
    ├── dispatcher.py            # 双端交付渲染器（生成客户核验工作台 report.html 与内部运营手册 internal_bd_ops.html）
    ├── frontend_assets.py       # 前端安全控制器、纯JS原生 OpenXML (.xlsx) 生成器、OWASP CSV防注入与无障碍焦点管理
    ├── compiled_css.py          # 预编译生产级 Tailwind CSS 样式表（彻底移除运行时 Play CDN 依赖）
    ├── growth_playbook.py       # 卖方能力档案预设（含跨赛道门控）与三档单赛道人工核验试点方案定义
    └── mock_data.py             # 10 条经 Hacker News 官方 Firebase/Algolia API 实盘核验的基准样本集
```

---

## 🚀 三、 快速运行与核验

### 1. 运行自动化审计测试套件
```bash
python3 test_suite.py -v
```

### 2. 生成客户核验工作台 (`report.html`) 与内部运营手册 (`internal_bd_ops.html`)
```bash
python3 main.py --demo
```

### 3. 前端安全与交付特性
- **显式导出控制**：提供独立的 `导出当前筛选 (N条)`（0 结果时自动禁用）与 `导出全库 (M条)` 按钮，杜绝静默扩圈误导。
- **真实 OpenXML `.xlsx` 与防公式注入 CSV**：内置零依赖纯前端 OpenXML `.xlsx` 构建器（显式 `inlineStr` 字符串类型、首行冻结 `ySplit="1"`、自动筛选器 `autoFilter`、自动换行 `wrapText="1"`），并对所有以 `=`, `+`, `-`, `@`, `\t`, `\r` 开头的单元格执行 OWASP 公式防注入转义。
- **无障碍与键盘交互**：抽屉与弹窗具备完整 `role="dialog"`、`aria-modal="true"`、关闭时 `hidden`/`inert` 移出可访问树、焦点捕获（Focus Trap）与恢复；分屏列表采用原生可聚焦 `<button>` 并支持 `↑/↓` 键滚动跟随。
