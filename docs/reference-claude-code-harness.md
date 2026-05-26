# Claude Code Harness 设计拆解：源码级深度

基于 Claude Code 逆向源码的 5 阶段 harness 设计拆解。每个阶段追踪真实调用链、展示关键数据结构、解释设计取舍。

---

## 怎么读这份文档

这份文档有三层信息，各自回答不同的问题：

- **代码块和调用链**：展示系统的具体实现——"它怎么做的"
- **💡 精妙之处**：解释为什么这样做是聪明的——"这个设计妙在哪"
- **设计决策**：解释为什么选了 A 方案而不是 B——"为什么不换个做法"

如果你只想快速理解设计思想，可以只读 💡 精妙之处。如果你想深入理解实现细节，再看代码块和调用链。

---

## 阶段 1：任务理解 + 工具就绪

**目标：让 agent 在第一次 API 调用前，就知道自己能做什么、不能做什么、面对的是谁。**

### 执行流程

启动时的信息组装链：

```
用户输入 → query.ts:queryLoop()
  ├─ systemPrompt 构建（含 CLAUDE.md 多层文件）
  ├─ tools.ts:getAllBaseTools() → 注册所有内置工具
  ├─ skills/bundledSkills.ts:registerBundledSkill() → 注册 skill 为 Command
  ├─ ToolSearchTool → 低频工具只暴露名称，按需加载 schema
  └─ utils/attachments.ts:getAttachmentMessages() → 注入上下文附件
```

工具注册的具体链路：`tools.ts` 中把所有 Tool 实例（BashTool、FileReadTool、FileEditTool 等）收集为一个数组。每个 Tool 实现一个统一接口：

```
Tool 接口的关键字段：
  name         — LLM 在 tool_use 中引用的标识符
  inputSchema  — Zod schema，用于验证 LLM 给出的输入
  isReadOnly() — 返回 boolean，决定能否并发执行
  call()       — 实际执行逻辑
  description()— 生成给用户看的权限弹窗描述
```

> 💡 **精妙之处**：统一接口意味着所有工具——不管是读文件、跑命令还是搜索代码——对系统来说"长得一模一样"。这就像你家里所有电器都用同一种插头：你不需要为每种电器设计一个插座，新工具想加入系统也只需要"做成这个插头的形状"就行。如果每个工具都有自己独特的调用方式，每加一个新工具就得改一遍调度逻辑，系统会越来越脆弱。

Deferred Tools 机制（`ToolSearchTool`）：工具注册时可以被标记为 deferred。这些工具只向 LLM 暴露名称和一行描述，不暴露完整 JSON Schema。当 LLM 决定调用时，必须先调用 ToolSearch 工具拉取完整定义，ToolSearch 返回完整 schema 后工具才可调用。

> 💡 **精妙之处**：这就像一个餐厅菜单只列菜名，不贴配料表。你 99% 的时间只需要扫一眼菜名就够了，只有真的要点那道菜时才需要看详情。如果把 40+ 个工具的完整说明全塞给 LLM，它的"注意力"会被稀释——就像你面前放 40 本操作手册，你反而什么都看不进去。这个设计把每个工具的 context 成本从 200-500 tokens 降到 20 tokens，省下来的空间留给真正重要的信息。

### 关键数据结构

```
ToolPermissionContext（权限上下文，每次工具调用前检查）:
  mode                — "default" | "plan" | "bypassPermissions"
  alwaysAllowRules    — 按来源分组的自动放行规则
  alwaysDenyRules     — 按来源分组的绝对禁止规则
  alwaysAskRules      — 需要用户确认的规则
  additionalWorkingDirectories — 允许操作的额外目录

ToolUseContext（贯穿整个查询生命周期的上下文）:
  options.tools       — 当前可用的所有工具数组
  options.mcpClients  — 已连接的 MCP 服务器
  abortController     — 用户按 Escape 时取消所有操作
  readFileState       — LRU 缓存，记录已读文件（避免重复）
  messages            — 完整消息历史
  contentReplacementState — 工具结果超限时的替换状态
```

> 💡 **精妙之处**：权限规则分成 allow/deny/ask 三类，而不是简单的"允许/禁止"二分法。这就像小区门禁：住户直接刷卡进（allow）、陌生人直接拒绝（deny）、快递员需要你按一下确认键（ask）。中间态"ask"的存在让你不必在"完全信任"和"完全禁止"之间做非此即彼的选择——大部分真实场景恰好在两者之间。

### 设计决策

**为什么权限规则按来源分组**（cliArg/session/localSettings/userSettings/projectSettings）：因为不同来源有不同的可信度。projectSettings 是 git 仓库里的文件，任何 clone 这个仓库的人都受其影响——所以它的 deny 规则优先级最高（防止恶意仓库授权危险操作）。session 规则是本次会话用户临时授权的，关闭后消失。

**为什么用 Deferred Tools 而不是全量注册**：实测 Claude Code 有 40+ 内置工具 + 用户的 MCP 工具。如果全部注册，每个工具的 JSON Schema 平均 200-500 tokens，光工具定义就吃掉 10-20K context。Deferred 把这个成本降到每个工具约 20 tokens（只有名字），需要时再付出完整 schema 的成本。

### 如果没有这层

Agent 没有身份、没有边界。它不知道你是设计师（可能给你写底层 C 代码），不知道哪些操作危险（可能 `rm -rf /`），不知道有哪些工具可用（要么全量塞进 context 浪费空间，要么遗漏能力）。

---

## 阶段 2：执行 + 分离评估

**目标：工具调用不是"LLM 说了就执行"，而是经过权限检查、Hook 评估、并发控制后才执行。**

### 执行流程

一次工具调用的完整链路（从 LLM 输出到结果返回）：

```
LLM 返回 tool_use block
  │
  ├─ toolOrchestration.ts:runTools()
  │   ├─ partitionToolCalls() — 把多个工具调用分成"可并发批次"和"串行批次"
  │   │   （判据：tool.isReadOnly() && tool.isConcurrencySafe()）
  │   └─ 对每个批次 → toolExecution.ts:runToolUse()
  │
  ├─ runToolUse() 内部流程：
  │   ├─ 1. inputSchema.safeParse() — Zod 验证输入
  │   ├─ 2. toolHooks.ts:runPreToolUseHooks() — 执行用户定义的前置 hook
  │   │      hook 可返回：block（阻止执行）/ allow / additional_context
  │   ├─ 3. useCanUseTool() — 权限检查（核心逻辑，详见下方）
  │   ├─ 4. tool.call() — 实际执行
  │   ├─ 5. toolHooks.ts:runPostToolUseHooks() — 后置 hook
  │   │      hook 可返回：block / stop_continuation / additional_context / updatedOutput
  │   └─ 6. processToolResultBlock() — 对结果做大小限制处理
  │
  └─ 结果作为 tool_result 追加到 messages，循环回 LLM
```

> 💡 **精妙之处**：注意这里有 6 个步骤，但真正"干活"的只有第 4 步 `tool.call()`。前面 3 步全是检查，后面 2 步是善后。这就像你去银行取钱：你以为核心动作是"拿钱"，但银行设计了身份验证、限额检查、流水记录一整套流程包裹住这个动作。如果只有"拿钱"这一步，那任何人拿着你的卡就能把钱取光。这 6 步的编排让一个不可信的 LLM 输出变成一个可控的安全操作。

权限检查（`useCanUseTool`）的三阶段决策：

```
hasPermissionsToUseTool()（静态规则匹配）
  │
  ├─ allow → 直接通过
  ├─ deny → 直接拒绝（返回错误给 LLM）
  └─ ask → 进入动态评估
       │
       ├─ handleCoordinatorPermission() — 如果是后台 worker，先让自动检查决定
       ├─ handleSwarmWorkerPermission() — swarm 模式下转发给 leader 决策
       ├─ Bash Classifier（LLM 分类器）— 对 bash 命令做安全分类
       │   （2秒超时，高置信度通过时跳过弹窗）
       └─ handleInteractivePermission() — 最终兜底：弹出用户确认弹窗
```

> 💡 **精妙之处**：权限检查是一个"漏斗"，从最快到最慢排列——静态规则匹配是微秒级的，分类器是秒级的，用户确认是不确定的（你可能去倒杯水才回来）。系统总是先尝试最快的决策方式，只有快速方式搞不定时才升级到慢的。这就像客服系统：常见问题 FAQ 秒回，复杂问题转人工。你不会为了一个 `git status` 命令等 2 秒分类器判断——规则表直接放行了。

### 关键数据结构

```
PermissionDecision（每次权限检查的结果）:
  behavior       — "allow" | "deny" | "ask"
  updatedInput   — hook 可能修改了输入（如路径重写）
  decisionReason — 说明为什么做此决定
    type: "rule" | "hook" | "classifier" | "mode" | "permissionPromptTool"
  suggestions    — 给用户的建议操作（如"允许此类命令"）

HookJSONOutput（用户定义 hook 的返回格式）:
  decision       — "allow" | "block" | "deny"（同步 hook）
  reason         — 给模型看的解释文字
  additionalContext — 注入到模型 context 的额外信息
  outputToAppend — 追加到工具输出的内容
  stopReason     — 阻止模型继续执行的原因
```

> 💡 **精妙之处**：Hook 不只能说"不行"（block），还能往 LLM 的 context 里塞信息（additionalContext）。这就像一个导师不只会打叉说"错了"，还会在旁边写"错在哪、该怎么改"。如果 hook 只能拦截而不能解释，LLM 下一轮只知道"这条路走不通"，但不知道该走哪条路——它可能换个姿势犯同样的错。能注入上下文的 hook 让"被拦截"本身变成了一次学习机会。

### 设计决策

**为什么执行和评估分离**：LLM 可能幻觉出一个危险命令（如 `rm -rf /`），如果"说了就执行"，后果不可逆。分离评估意味着即使 LLM 100% 确信该执行，系统仍然有一个独立的检查点。

**为什么 Hook 既能 block 也能注入上下文**：纯拦截（block）只能说"不行"。但真实场景中，hook 往往知道"为什么不行"以及"应该怎么做"。比如 lint hook 发现代码格式不对，它既阻止提交，又把 lint 错误信息注入 context——让 LLM 下一轮能修复。

**为什么工具执行区分并发和串行**：FileRead 这种只读操作可以 10 个并发跑，不会互相影响。但 FileEdit 必须串行——如果两个 edit 并发写同一个文件，结果不确定。`partitionToolCalls()` 把连续的只读操作合成一批并发，遇到写操作则切割为单独的串行步骤。最大并发度默认 10（`CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY`）。

### 如果没有这层

每次 LLM 说"执行 `git push --force`"就真的执行了。没有 hook 意味着你不能在执行前注入 lint 检查、安全扫描、格式校验。没有并发控制意味着 LLM 同时编辑 5 个文件会产生竞态条件。

---

## 阶段 3：失败修复策略

**目标：失败不是简单重试，而是诊断"缺了什么"然后调整策略。**

### 执行流程

失败处理分布在多个层级：

```
query.ts:queryLoop() 的 while(true) 循环
  │
  ├─ API 层失败：
  │   ├─ prompt_too_long → 触发 reactive compact（砍掉最旧的消息组重试）
  │   │   reactiveCompact.ts → truncateHeadForPTLRetry()
  │   │   最多重试 MAX_PTL_RETRIES=3 次
  │   ├─ max_output_tokens → 恢复循环（最多 3 次）
  │   │   不是简单重发，而是继续让 LLM 从断点输出
  │   └─ rate_limit / 500 → withRetry.ts 的指数退避
  │
  ├─ 工具层失败：
  │   ├─ 权限被拒 → executePermissionDeniedHooks()
  │   │   hook 可返回 additional_context 告诉 LLM "为什么被拒、该怎么做"
  │   ├─ 执行报错 → runPostToolUseFailureHooks()
  │   │   hook 可注入诊断信息（如 stack trace 分析）
  │   └─ 输入验证失败 → formatZodValidationError() 返回具体哪个字段不对
  │
  ├─ Hook 层阻止：
  │   ├─ PreToolUse hook 返回 block → 工具不执行，原因注入 context
  │   ├─ PostToolUse hook 返回 stop_continuation → 整个 query 停止
  │   └─ Stop hook 失败 → executeStopFailureHooks() 处理停止失败
  │
  └─ 自动压缩失败：
      ├─ MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES=3 → 停止重试（熔断器）
      └─ 失败原因：compact 请求本身 prompt_too_long → truncateHeadForPTLRetry
```

> 💡 **精妙之处**：注意每种失败的处理方式都不一样——不是统一的"报错→重试"。`prompt_too_long` 的对策是"砍掉旧消息腾空间"，`max_output_tokens` 的对策是"让 LLM 从上次中断处继续说"，权限被拒的对策是"告诉 LLM 为什么不行"。这就像一个有经验的司机：轮胎没气了换轮胎，油没了加油，导航错了重新规划路线——而不是所有问题都靠"重启车"解决。

关键的「不是重试而是调整」设计：

```
denialTracking.ts 的拒绝追踪：
  连续 N 次被拒后（DENIAL_LIMITS），自动 fallback 到弹窗模式
  "如果自动化一直不通过，说明规则不够用，得让人来决定"

Bash Classifier 的超时机制：
  分类器有 2 秒 grace period
  超时 → 不是重试分类器，而是直接弹出用户确认
  "分类器不确定时，退化到人工决策而不是卡住"
```

> 💡 **精妙之处**：这两个机制的共同点是"承认自动化有边界"。系统不会永远坚持自动决策——当它发现自己搞不定（连续被拒/分类超时），就主动把球踢给你。这就像一个聪明的实习生：ta 会尽量自己解决问题，但如果同一类问题连续卡了 3 次，ta 不会第 4 次还死磕，而是来问你"这个我搞不定，你来定"。反过来，如果系统永远不升级到人工决策，你会看到它在同一个坑里原地打转。

### 关键数据结构

```
AutoCompactTrackingState（自动压缩的状态追踪）:
  compacted              — 本轮是否已压缩
  turnCounter            — 当前轮次
  turnId                 — 唯一标识
  consecutiveFailures    — 连续失败次数（熔断器计数）

DenialTrackingState（权限拒绝追踪）:
  denialCounts    — 每个工具被拒次数
  successCounts   — 每个工具成功次数
  → shouldFallbackToPrompting() — 判断是否该退化到人工模式
```

> 💡 **精妙之处**：系统不只记住"失败了几次"，还记住"每个工具分别失败了几次"。这让退化决策是精准的：如果只有 `rm` 命令反复被拒，只有 `rm` 退化到人工确认，其他工具照常自动执行。这就像你管一个团队：某个人连续 3 次交付出问题，你只盯紧 ta 的交付，不会因此要求整个团队每件事都先过你审批。

### 设计决策

**为什么用熔断器而不是无限重试**：之前的数据显示 1,279 个 session 出现 50+ 次连续压缩失败（最高 3,272 次），浪费约 25 万次/天 API 调用。熔断器在 3 次失败后停止，因为「如果连续 3 次压缩都失败，说明问题不在运气，而在于 context 已经无法被进一步压缩」。

**为什么权限拒绝有 fallback 机制**：自动模式（Auto Mode/YOLO）依赖分类器判断命令安全性。但分类器可能误判。如果某个工具被连续拒绝 N 次，说明分类器对这类操作没有信心——此时退化到让用户手动确认，比卡死在循环里好。

### 如果没有这层

Agent 卡死在循环中：API 报错就无限重试，权限拒绝就反复尝试同样的命令，压缩失败就持续浪费 API 调用。更关键的是，失败信息不会流回给 LLM——它不知道「为什么失败」，所以无法调整策略。

---

## 阶段 4：Context 生命周期管理

**目标：在长时间运行中防止信息腐烂——既不丢失关键信息，又不让 context 膨胀到不可用。**

### 执行流程

Context 管理是多层次的，从细粒度到粗粒度：

```
每轮 API 调用前（query.ts 的 while(true) 内部）：
  │
  ├─ 1. applyToolResultBudget() — 单条工具结果的大小限制
  │      超过 maxResultSizeChars 的结果被替换为摘要
  │      替换是持久化的（下次 resume 仍能看到）
  │
  ├─ 2. snipCompact (HISTORY_SNIP) — 删除不影响连续性的旧消息
  │      比如早期的 file_read 结果（文件后来被改了）
  │
  ├─ 3. microCompact — 把旧的工具输出压缩为摘要
  │      保留 tool_use_id（API 要求 user-assistant 交替）
  │      内容替换为简短的 "[file content unchanged]" 或摘要
  │
  ├─ 4. contextCollapse (CONTEXT_COLLAPSE) — 把一段对话折叠为一条摘要
  │      类似 Git squash：多个 commit 变一个
  │
  └─ 5. autoCompact — 最重量级的压缩
       触发条件：token 用量超过阈值（context window - 13K buffer）
       │
       ├─ executePreCompactHooks() — 通知 hook "要压缩了"
       ├─ compact.ts:compactConversation()
       │   ├─ stripImagesFromMessages() — 移除图片（摘要不需要）
       │   ├─ stripReinjectedAttachments() — 移除会重新注入的附件
       │   ├─ 用一个 forkedAgent 调用 LLM 生成摘要
       │   │   prompt 要求包含：用户意图、关键文件、错误修复、待办任务
       │   └─ 摘要替换所有旧消息，插入 compact_boundary 标记
       ├─ buildPostCompactMessages() — 重新注入关键信息
       │   ├─ 最近修改的文件（最多 5 个，每个最多 5K tokens）
       │   ├─ 当前活跃的 skill 内容（每个最多 5K，总计最多 25K）
       │   ├─ plan 文件内容
       │   └─ MCP 指令 delta、agent 列表 delta
       └─ executePostCompactHooks() → processSessionStartHooks()
           重新执行 SessionStart hook（重置 session 状态）
```

> 💡 **精妙之处**：5 个压缩层级就像你收拾房间的策略——不是等房间乱到不能住了才大扫除。第 1 层是"随手把大件垃圾丢掉"，第 2 层是"过期的东西扔掉"，第 3 层是"把散落的东西收进抽屉"，第 4 层是"把一整个区域打包归档"，第 5 层才是"整个房间彻底清理重新开始"。如果只有最后一层，你的 context 会突然从"满满当当"跳到"几乎什么都没了"——中间状态的渐进式清理让信息丢失是可控的、渐进的。

> 💡 **精妙之处**：`snipCompact` 删掉的是"文件后来被改了的旧读取结果"。想想看：你 10 分钟前读了一个文件，后来改了它 3 次。那 10 分钟前的版本不只是没用，它是有害的——如果 LLM 参考了那个过期内容来做决策，结果一定是错的。主动删掉过期信息比留着它让 LLM 困惑要好得多。

Memory 系统的读写时机：

```
写入时机：
  - 用户手动触发 memory 工具
  - extractMemories 服务自动提取（后台 agent）
  - session_memory compact 时提取会话记忆

读取时机（query.ts 入口处预取）：
  startRelevantMemoryPrefetch()
    → findRelevantMemories()
      → scanMemoryFiles() — 扫描 ~/.claude/memory/ 下所有 .md 文件
      → selectRelevantMemories() — 用 Sonnet 做相关性判断（最多选 5 个）
    → 结果作为 attachment 注入到消息中
  时机：与模型推理并行执行（prefetch），不阻塞主流程
```

> 💡 **精妙之处**：Memory 不是"全部塞进去"，而是用一个小模型先筛选出最相关的 5 条。这就像你问助理一个问题，ta 不会把整个文件柜搬来——而是先花 2 秒想"这个问题跟哪几份文件有关"，然后只拿那几份。如果把所有记忆都塞进 context，跟不筛选的效果几乎一样差——太多无关信息照样稀释 LLM 的注意力。

### 关键数据结构

```
CompactPrompt（压缩指令的核心要求）:
  包含 9 个必填章节：
  1. Primary Request and Intent — 用户的完整请求
  2. Key Technical Concepts — 技术概念和框架
  3. Files and Code Sections — 具体文件和代码片段
  4. Errors and Fixes — 遇到的错误和修复方法
  5. Problem Solving — 已解决的问题
  6. All User Messages — 所有用户消息（不含工具结果）
  7. Pending Tasks — 待完成任务
  8. Current Work — 当前正在做的事
  9. Optional Next Step — 下一步（必须与最近请求直接相关）

MemoryHeader（memory 文件扫描结果）:
  filename    — 相对路径
  filePath    — 绝对路径
  mtimeMs     — 最后修改时间
  description — frontmatter 中的描述
  type        — memory 类型（如 "preference"、"procedure" 等）

MEMORY.md 入口文件的限制：
  MAX_ENTRYPOINT_LINES = 200 行
  MAX_ENTRYPOINT_BYTES = 25,000 字节
  超限则截断并附加警告
```

> 💡 **精妙之处**：CompactPrompt 强制要求 9 个章节，这不是格式洁癖，而是防止压缩时"只记住最近的事"。没有这个模板，LLM 做摘要时会本能地侧重最新信息——10 分钟前用户说的核心目标可能被一句话带过。9 个章节就像一份必填问卷：你可以某章写"无"，但你不能跳过"用户的完整请求"和"待完成任务"这两项。这确保了即使压缩后，系统仍然知道"你要干什么"和"还剩什么没干"。

### 设计决策

**为什么压缩是多层次的而不是一次性**：不同信息的「保质期」不同。一个文件的读取结果在文件被修改后就过期了（snip 可以安全删除）；但用户说过的话永远重要（只有 full compact 才能摘要化）。多层次设计让每层处理自己擅长的过期类型。

**为什么 compact 后要重新注入文件和 skill**：压缩后 LLM 失去了所有细节。如果不重新注入最近修改的 5 个文件，LLM 下一轮回答时会说"让我重新读取文件"——这浪费一个工具调用。重新注入的预算控制（50K tokens 总计）是在「省 context」和「省工具调用」之间的平衡点。

**为什么 Memory 读取用 prefetch 而不是阻塞**：Memory 查询需要调用一个 side query（用 Sonnet 判断相关性），耗时 1-3 秒。如果阻塞在主流程里，用户会明显感到延迟。Prefetch 让这个查询与模型推理并行，绝大多数情况下模型还没生成完第一个 token，memory 就已经就绪了。

### 如果没有这层

长对话必然崩溃：要么 token 超限 API 报错，要么关键信息被挤出 context window 导致 LLM 忘记之前做过什么。用户会反复看到 agent 说"让我重新看看这个文件"——已经读过 3 次了。Memory 系统缺失则意味着每次新会话都是白纸，之前学到的偏好和教训全部丢失。

---

## 阶段 5：监控 + 持续改进

**目标：追踪历史错误模式，用数据反哺 harness 设计决策。**

### 执行流程

Claude Code 的监控和改进分为运行时追踪和事后分析：

```
运行时追踪（贯穿 query loop）：
  │
  ├─ permissionLogging.ts — 每次权限决策都记录
  │   logPermissionDecision({ tool, input, decision, source })
  │   追踪：哪些工具被拒最多？哪些规则触发最频繁？
  │
  ├─ analytics/index.ts:logEvent() — 结构化事件
  │   tengu_post_tool_hooks_cancelled — hook 被取消
  │   tengu_post_tool_hook_error — hook 执行出错
  │   tengu_memdir_prefetch_collected — memory 预取耗时
  │   tengu_autocompact_* — 自动压缩的触发和结果
  │
  ├─ telemetry/sessionTracing.ts — OpenTelemetry 级别追踪
  │   startToolSpan() / endToolSpan() — 每个工具调用的耗时
  │   startToolBlockedOnUserSpan() — 等待用户确认的时间
  │   startHookSpan() — hook 执行耗时
  │
  ├─ bootstrap/state.ts — 会话级计数器
  │   addToTurnHookDuration() — hook 总耗时（用于决定是否显示 timing）
  │   addToToolDuration() — 工具总耗时
  │   getTotalInputTokens() / getTotalOutputTokens() — token 消耗追踪
  │
  └─ utils/sessionStorage.ts — 持久化 transcript
      每个 session 的完整对话记录存储在 ~/.claude/sessions/ 下
      用于 /resume 恢复和事后分析

反哺 harness 设计的数据通路：

  GrowthBook（特性开关服务）
    → getFeatureValue_CACHED_MAY_BE_STALE()
    → 控制：是否启用 autocompact、classifier 策略、memory prefetch 等
    → 基于线上数据 A/B 测试后逐步打开

  Hook 系统本身就是改进通路：
    用户发现 agent 反复犯同一个错 → 写一个 PreToolUse hook 拦截
    示例：agent 总是用 rm 删文件 → hook 拦截并告诉它用 trash
    "把线上错误模式固化为配置规则"
```

> 💡 **精妙之处**：监控系统特意区分了"工具本身的执行时间"和"等待用户确认的时间"（`startToolBlockedOnUserSpan`）。这个区分看似微小但极其关键——如果你发现某个操作平均耗时 15 秒，问题可能是"工具慢"也可能是"用户去上厕所了才回来点确认"。不区分的话你会优化错方向，花大力气优化一个其实只要 200ms 的工具，实际瓶颈是权限弹窗太频繁。

> 💡 **精妙之处**：Hook 作为改进通路，把"发现问题到修复问题"的周期从"等开发团队发版（天/周）"缩短到"自己写条规则（分钟）"。这就像从"向物业投诉等维修"变成"自己手边有工具箱"。你发现 agent 总爱用 `rm` 删文件？不用等 Anthropic 下个版本修复——写一条 hook 规则说"遇到 rm 就拦截，提示用 trash"，立即生效。这不只是便利，这是把产品改进的权力从开发者转移到了用户手中。

### 关键数据结构

```
Hook 执行事件（hookEvents.ts）:
  HookStartedEvent  — hookId, hookName, hookEvent
  HookProgressEvent — 实时 stdout/stderr 输出
  HookResponseEvent — exitCode, outcome(success/error/cancelled)

Session Transcript（持久化的会话记录）:
  存储位置：~/.claude/sessions/{sessionId}/
  包含：所有 messages、工具调用结果、compact boundary、metadata
  用途：
    - /resume 命令恢复会话
    - 事后审计 agent 行为
    - 调试失败场景

tokenStats（context 分析）:
  analyzeContext() → tokenStatsToStatsigMetrics()
  追踪：system prompt 占多少、messages 占多少、tools 占多少
  用于决定 compact 阈值是否需要调整
```

> 💡 **精妙之处**：Session Transcript 的完整记录不只是为了 debug——它让 `/resume` 成为可能。你下午跟 agent 聊到一半去开会了，晚上回来输入 `/resume`，整个对话状态完美恢复。这背后的前提是每一步都被忠实记录了。如果只记最终结果不记过程，恢复时 agent 会丢失"它是怎么走到这一步的"这个关键上下文，恢复后的行为会跟中断前不一致。

### 设计决策

**为什么用 feature gate 而不是硬编码策略**：Claude Code 服务数百万用户，不同场景的最优策略不同。比如 autocompact 的阈值，太早压缩会丢信息，太晚压缩会导致 API 报错。通过 GrowthBook 远程控制参数，团队可以基于 A/B 测试的数据逐步调优，而不是靠直觉拍一个数字。

**为什么 Hook 是改进的主要通路**：传统做法是「发现问题→改代码→发版」，周期是天/周级别。Hook 让用户「发现问题→写一行 shell 命令→立即生效」。这不只是便利性，而是把「持续改进」的权力从开发团队下放到每个用户。你不需要等 Anthropic 发版来修复你的特定问题。

**为什么工具执行有 slow-phase 日志阈值**（2秒）：如果权限检查或 hook 执行超过 2 秒，说明这个环节已经从「无感」变成「用户能感知到卡顿」。记录这些事件让团队知道哪些流程需要优化。阈值选 2 秒是因为匹配了 BashTool 的进度显示阈值——如果命令跑了 2 秒还没完，显示 spinner。

### 如果没有这层

你不知道 agent 为什么变慢了（是 hook 太多？是 compact 太频繁？还是 API 限流了？）。没有 transcript 意味着出问题时无法事后复盘。没有 feature gate 意味着所有策略变更都要发版，无法快速回滚。没有 hook 作为改进通路意味着每个错误模式都要等开发团队修代码。

---

## 总结：5 层之间的关系

```
阶段 1（任务理解）→ 定义 agent 的能力边界和身份
    ↓
阶段 2（执行评估）→ 在边界内安全执行，Hook 作为外部裁判
    ↓
阶段 3（失败修复）→ 失败时诊断原因，调整策略而非盲目重试
    ↓
阶段 4（Context 管理）→ 长时间运行中保持信息新鲜和可用
    ↓
阶段 5（监控改进）→ 用数据反哺上面 4 层的策略参数
```

核心设计哲学：**每一层都有独立的「退化模式」**。分类器不确定→退化为用户确认。压缩失败→熔断停止。Memory 查询超时→跳过不阻塞。这确保了系统在任何单点故障时都能继续工作，只是质量下降，而不是完全停机。

> 💡 **精妙之处**：整个系统最深层的设计哲学是"优雅降级"而不是"追求完美"。每一层都预设了"如果我搞砸了怎么办"的退路。这就像一栋好的建筑设计：电梯坏了有楼梯，主电源断了有备用发电机，消防喷淋失效了还有防火门。没有哪一层是"如果这层挂了整栋楼就塌了"的单点。这让你作为用户几乎感知不到系统内部的故障——它可能在某一刻用了一个不那么优雅的方案，但它始终在工作。
