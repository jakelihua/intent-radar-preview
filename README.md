# IntentRadar v3.2 — Production Pilot 修复版

基于 `c38cef3` 修复第三轮复审问题。工作台用于发现、研究和核验公开社区替换需求。**分数仅排序；品牌预设不证明产品能力匹配；历史样本不计当期交付。**

## 运行

要求 Python 3.9+。测试环境另需 Node 20+。

```bash
python3 -m pip install -r requirements.txt
python3 main.py --demo
```

`--demo` 禁用模型调用，生成历史核验工作台 `report.html`；公开预览 `index.html` 使用同一份生成内容。实时模式不混入任何历史样本：

```bash
python3 main.py --config config.json --html report_local.html
```

每个客户必须使用独立且明确的 `client_id`；未提供时禁止启用 Webhook。只有四阶段通过的当期记录可以进入已配置的 Webhook。默认未配置卖方核验档案，因此不会自动交付。实时模式开启 `use_llm_api` 且存在模型密钥时会调用模型；可设置为 `false` 使用确定性判研。不要将密钥、Webhook 或客户核验配置提交到公开仓库。

## 四步资格与人工核验

1. 确认买方痛点和软件标的。厂商推广不通过。
2. 必须有正向替换评估证据；普通抱怨、明确不替换、无决定权停留在阶段 1。
3. 在卖方档案中填写真实身份、核准能力和限制，再在**单条详情**中逐项核实必选能力，填写核验人和依据。任一必选能力不支持，选择“不匹配”；尚未确认，保持“待核验”。
4. 另行核实联系人参与选型且可推进，记录联系 URL 和权限核验依据。还必须满足当期 30 天窗口、完整内容、生产数据集等条件。历史样本最高阶段 3。

核验记录绑定 `(source, source_id, content_hash, seller_snapshot)`，有效期 30 天；修改原帖或卖方能力会使旧记录失效。仅有关键词或一段能力宣传不能通过阶段 3。权限和预算的推断标签不能替代阶段 4 的联系人核验。

网页核验记录仅在当前会话生效。使用“导出核验配置”，在私有环境载入：

```bash
python3 main.py --seller-profile intent-radar-seller-review.json --html report_local.html
```

这会将 JSON 中的 `seller_profile` 用于本轮判研。不要编辑版本哈希以绕过失效检查。前端与 Python 消费同一组后端事实，阶段与策略的跨语言契约由测试覆盖。模型可以保守降级，不能升级资格；外发文本由结构化已核准事实确定性生成，不采用模型自由话术。

## 采集、时效和状态

- 每个来源在独立子进程顺序执行查询，共享该来源限速与冷却。父进程截止时终止并回收未完成的进程；没有遗留 HTTP 线程阻止 CLI 退出。
- 支持数字和 HTTP-date `Retry-After`；长冷却延期，等待速率间隔后再次检查冷却和截止时间。冷却期限持久化到 SQLite。
- 缺失、非法、未来发布时间均不可交付。每次推送重新评估时效。
- Dev.to 列表只作发现，额外请求详情；详情失败标记内容不完整。Google News RSS 是摘要研究材料，不宣称新闻全文，不自动交付。
- SQLite 保存原文版本、交付状态；配置默认路径为仓库下 `.intent-radar/state.sqlite3`，已从 Git 和 Pages 排除。相对路径按配置文件目录解析。`INTENT_RADAR_STATE_DIR` 可改变未指定路径时的默认目录。
- 来源失败、限流延期和正常空结果分别展示。生产任务应监控来源状态，不能把全源失败解释为没有市场需求。

## 交付与异常处理

发送前以 `(source, source_id, client_id:channel, version)` 在 SQLite 事务中原子认领。只有认领成功者发送；已交付版本只增不减。

状态为 `sending / sent / failed / uncertain`。明确被接收端拒绝的任务最多可认领 3 次；网络超时、无有效回执或进程中断**不自动重发**，避免对方已收到却再次发送。没有接收端幂等协议时无法同时保证绝不重复与绝不遗漏，本版选择保留不确定状态供人工核对。

```bash
python3 main.py --list-deliveries
# 在接收端核实后，二选一；以下命令本身不会发送消息：
python3 main.py --resolve-delivery TOKEN --resolution sent
python3 main.py --resolve-delivery TOKEN --resolution not-sent
python3 main.py --backup-state backups/intent-radar-state.sqlite3
```

`not-sent` 仅在确认未收到后使用，允许后续任务重试。不得仅因为“等得久”就清除认领。备份使用 SQLite backup API，连接在任务结束时关闭；重启后复用相同数据库。升级已有服务时，先将 `state_db_path` 指向旧库，备份到新持久化路径，再切换配置；保持原有 `client_id`，避免丢失既有交付记录。

## 验证与部署

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m unittest test_suite test_regressions -v
npm ci
npx playwright install chromium
python3 main.py --demo
cp report.html index.html
npm run test:browser
```

回归覆盖普通抱怨、能力不匹配、版本失效、历史/未来/不完整内容、模型越权话术、跨连接并发投递、歧义超时、冷却并发变更、可终止采集进程、真实进程序列化、Python/JS 策略一致、存储回退和 XLSX 实际读取。浏览器测试覆盖焦点、零结果导出与人工核验流程。

GitHub Pages 部署必须先通过 Python、Node 和 Chromium 检查，只打包 `index.html`、`report.html` 和 `.nojekyll`。内部 BD 手册写入系统临时目录，不进入公开站点。私有客户配置与状态库应部署在受控运行环境；公开预览仍为历史演练数据。
