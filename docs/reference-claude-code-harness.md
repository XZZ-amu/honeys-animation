# Claude Code Harness 拆解：5 阶段参照

以 Claude Code 的实际配置为参照物，拆解一个成熟 agent harness 的设计。每个阶段指出具体机制、设计原因、缺失后果。

---

## 阶段 1：任务理解 + 工具就绪

**让 agent 知道做什么、有什么可用。**

### 具体机制

Claude Code 用三层文件构建 agent 的"任务理解"：

1. **全局 CLAUDE.md**（`~/.claude/CLAUDE.md`）— 定义用户是谁、协作原则、写代码铁律。相当于"这个人的通用操作手册"。例如你的文件里写了"产品设计师，不懂代码"、"禁止试错式修复"，agent 每次启动都读取这些。

2. **项目 CLAUDE.md**（项目根目录）— 定义当前项目做什么、约束是什么。比如 honeys-animation 项目里写了"输出是单个 .html 文件"、"每次练习聚焦一个阶段"。

3. **工具权限表**（`settings.json` 的 `permissions`）— 三个列表：allow（自动放行）、deny（绝对禁止）、ask（每次问用户）。这不是"列出工具"这么简单，而是**划定能力边界**。比如 `Bash(rm -rf:*)` 在 deny 里，意味着 agent 永远不会删整个目录；`Bash(git push --force:*)` 在 ask 里，意味着破坏性操作必须人工确认。

4. **Deferred Tools + ToolSearch** — 工具不是一次性全加载的。低频工具只暴露名称，agent 需要时再拉取完整定义。这防止 context 被 50 个工具的 schema 塞满。

### 为什么这么设计

agent 不是人，没有"常识"来推测你要什么。如果不显式写明"我是产品设计师"，它可能给你写技术文档；如果不写明"输出是 .html 文件"，它可能给你输出 React 组件。权限表则是防御性设计——agent 有能力做很多事，但不是所有能力都该开放。

### 如果没有这层

agent 每次启动都是白纸。你得反复说"我不懂代码"、"别用技术黑话"、"别删我文件"。而且它可能在修 bug 时 `rm -rf` 整个项目目录，或者 `git push --force` 覆盖队友的代码。

---

## 阶段 2：执行 + 分离评估

**做事的和判断的必须是不同角色。**

### 具体机制

1. **PreToolUse Hook — edit-gate.sh** — 每次 agent 要编辑文件时，harness 注入一段"门控提醒"，强制 agent 自问：你走完诊断流程了吗？你能说清为什么这样改吗？用户确认了吗？这不是 agent 自己的"良心"，而是系统级强制检查点。

2. **子 Agent 审查机制**（写在 CLAUDE.md 铁律里）— "改代码必须派子 Agent 审查"。子 Agent 的职责是独立定位根因、评估副作用、检查影响范围。两个结论一致再动手。这实现了"执行者"和"评估者"的角色分离。

3. **测试计划分层**（写在 CLAUDE.md 铁律里）— 自验层（agent 自己能跑通的）必须全过才交付；验收层（需要用户操作的）只做最终确认。用户是裁判，不是测试机。

4. **memory 中的强化**（`feedback_subagent_output_is_hypothesis.md`）— 明确记录"子 Agent 的输出是假设不是结论"，必须实测验证。这防止评估者的判断被不加验证地采信。

### 为什么这么设计

同一个 agent 既执行又评估，等于让学生自己给自己阅卷——它倾向于认为自己写的代码是对的。分离评估强制引入"第二双眼睛"。edit-gate 则是在代码级别拦截冲动行为，不靠 agent 自律。

### 如果没有这层

agent 修 bug 时会陷入"改一下试试→不行→再改→不行"的死循环（你的 memory 里记录了修一个 bug 十几次没成功的真实案例）。没有门控，agent 想到就改；没有子 Agent 审查，错误假设没人挑战。

---

## 阶段 3：失败修复策略

**不是重试，而是问"缺了什么能力"。**

### 具体机制

1. **diagnose skill** — 一个完整的结构化诊断流程：先建反馈循环（找到可复现的 pass/fail 信号）→ 复现 → 生成 3-5 个假设并排序 → 逐个验证 → 修复 → 回归测试。明确写了"不允许没有反馈循环就开始猜"。

2. **PostToolUseFailure Hook** — 当 Bash 命令执行失败时，harness 触发通知（在你的配置中是 peon-ping 声音通知）。这确保失败不会被默默吞掉。

3. **"禁止试错式修复"铁律** — 写在全局 CLAUDE.md 里，每次启动都加载。修 bug 前必须先证明"我知道为什么坏了"，确认后再动手。

4. **edit-gate 的调试拦截** — 如果当前是修 bug 场景，agent 必须已经调用过 diagnose skill。配置里的原话："「我觉得根因很明显不需要 diagnose」不是合法理由。上次你就是这么想的然后试错了三轮。"

### 为什么这么设计

LLM 的默认倾向是"我觉得问题在这里，改一下"。这在简单问题上够用，但复杂 bug 有多层原因，盲改只会越改越乱。diagnose skill 的核心不是"教 agent 调试"，而是**强制它慢下来、系统化**——先建反馈循环，再假设，再验证。

### 如果没有这层

agent 会反复用同一个错误假设修同一个 bug，每次改动都引入新问题。你的 memory 里记录了真实案例：agent 在错误假设"missing value 导致列表拼接"上修了多轮，实际根因是"trim 吃掉了开头换行导致 split 模式不匹配"。如果不强制走诊断流程，这种死循环会反复发生。

---

## 阶段 4：Context 生命周期管理

**长时间运行中防止信息腐烂。**

### 具体机制

1. **context-status.sh（statusLine）** — 每 10 秒刷新一次，显示当前 context 使用量（如"🟡 ctx 450k / 1000k (45%)"）。当接近上限时变红，提醒用户/agent 该做 compact 了。

2. **PreCompact Hook** — 在 context 被压缩前触发通知。这是一个"你即将丢信息"的警报点，可以在此时决定哪些内容需要沉淀到持久存储。

3. **Memory 系统**（`~/.claude/projects/*/memory/`）— 跨 session 的持久记忆。每条记忆有 name、description、type、来源 session。但不是什么都存——memory-audit skill 有铁律："NEVER store surface-level observations"，只存深层 insight。

4. **memory-audit skill 的 SAVE 流程** — 存记忆前必须：提取本质 → 用户确认 → 查重（跟 CLAUDE.md 和已有 memory 对比）→ 决定存哪里。防止 memory 变成垃圾场。

5. **用户定义的沉淀原则**（memory 里的 `feedback_context_management.md`）— "沉淀概要时用户先定方向，Claude 按方向筛选，不是全列出来让用户挑。"

### 为什么这么设计

context window 是有限的（即使 1M token）。对话越长，早期信息被稀释、后期信息冲突早期决策。如果不主动管理，agent 会"忘记"10 分钟前确认过的方向，或者用过期信息做决策。Memory 系统则解决跨 session 的信息延续问题。

### 如果没有这层

长对话后期 agent 会开始"跑偏"——重复问已确认的问题，或者做出跟早期决策矛盾的行为。跨 session 时更严重：每次新对话都从零开始，之前踩过的坑会重新踩。你的 memory 里有 19 条经验记录，如果没有这套系统，这些经验每次都得重新"教"一遍。

---

## 阶段 5：监控 + 持续改进

**追踪历史错误模式，反哺 harness 设计。**

### 具体机制

1. **rules/lessons-learned.md** — 跨项目的"踩坑记录"。按类型分类（沟通类、执行类），每条记录有"坑"和"教训"。这不是 agent 自动学的，是用户主动沉淀的改进。

2. **memory 中的 feedback 文件** — 如 `feedback_diagnose_before_fix.md`、`feedback_subagent_output_is_hypothesis.md`，每个都来自一次真实失败。格式统一：What → Why（具体日期和事件）→ How to apply。这些记录会在每次 session 被加载，成为 agent 行为约束。

3. **对话收尾复盘机制**（写在 CLAUDE.md 里）— "对话收尾时做双向复盘：我做得好和不好的，你做得好和不好的。复盘完问：有需要沉淀的吗？"这是一个系统化的反馈收集触发点。

4. **hooks 的迭代** — 比如 edit-gate 里那句"上次你就是这么想的然后试错了三轮"，这是根据历史失败模式写的。hooks 本身就是历史教训的产物。

5. **Settings 备份**（`settings.json.bak.*`）— 配置变更有历史记录，可以追溯什么时候加了什么规则、为什么加。

### 为什么这么设计

harness 不是一次设计好就不动的。用户和 agent 的协作模式会随项目演变，新的错误模式会出现。如果不记录和反哺，同样的错误会以不同面貌反复出现。每条 feedback memory 本质上是一条"补丁"——修补 harness 中被证明不够的地方。

### 如果没有这层

harness 会停留在"v1"状态，而实际使用中不断暴露新问题。你的配置里有大量来自真实失败的规则（比如"禁止试错式修复"来自 2026-05-02 的十几次失败修复，"子 Agent 输出是假设"来自 2026-05-03 的误诊事件）。没有持续改进机制，这些教训不会变成系统约束，下次还会犯。

---

## 总结：如果你要设计一个新 agent harness

| 阶段 | 你需要解决的核心问题 | Claude Code 用什么解决的 |
|------|---------------------|------------------------|
| 1. 任务理解 | agent 不知道用户是谁、项目约束是什么、哪些能力能用 | 多层 CLAUDE.md + permissions allow/deny/ask + deferred tools |
| 2. 分离评估 | 同一个 agent 自己做自己评，倾向于肯定自己 | edit-gate hook（系统级拦截）+ 子 Agent 审查 + 测试分层 |
| 3. 失败修复 | agent 默认倾向是盲改重试 | diagnose skill（结构化流程）+ edit-gate 强制调用 + 铁律禁止试错 |
| 4. Context 管理 | 长对话信息腐烂、跨 session 记忆丢失 | statusLine 实时监控 + memory 系统 + memory-audit 质量控制 |
| 5. 持续改进 | 同样的错误反复出现 | lessons-learned + feedback memory + 复盘触发 + hooks 迭代 |
