# 创作类 AI Agent 开源项目调研

> 调研目标：找到值得拆解的创作类 AI agent 项目，学习其 harness 设计思维
> 调研日期：2026-05-26

---

## 候选项目列表

### 1. ComfyUI（Comfy-Org/ComfyUI）
- **Star**: 114k
- **定位**: 基于节点图的 diffusion model 工作流引擎
- **考虑理由**: 最成熟的创作类 workflow orchestration 系统，有完整的 DAG 执行引擎、缓存系统、验证层、错误处理
- **结论**: **最终推荐 #1** — 最佳 harness 设计参照物

### 2. Pixelle-Video（AIDC-AI/Pixelle-Video）
- **Star**: 19.7k
- **定位**: AI 全自动短视频引擎（文案 → 配图 → 逐帧 → 合成）
- **考虑理由**: 清晰的 Template Method 模式 pipeline、PipelineContext 状态管理、多 pipeline 变体支持、image/video analysis 反馈服务
- **结论**: **最终推荐 #2** — 最佳创作管线参照物，架构跟动画场景高度相关

### 3. MoneyPrinterTurbo（harry0703/MoneyPrinterTurbo）
- **Star**: 57.9k
- **定位**: 一键生成短视频（LLM 文案 + 素材采集 + TTS + 字幕 + 合成）
- **考虑理由**: 多 provider 抽象、完整管线
- **排除理由**: 架构相对简单，更像"多 API 串联"而非 harness 设计。没有质量评估反馈循环，没有执行图概念

### 4. RPG-DiffusionMaster（YangLing0818/RPG-DiffusionMaster）
- **Star**: 1.8k（ICML 2024 论文）
- **定位**: LLM 驱动的多区域图像生成（Recaptioning → Planning → Generating）
- **考虑理由**: LLM + Diffusion 协调、区域规划
- **排除理由**: 偏研究论文实现，没有 production harness 设计（无错误处理、无反馈循环、无持久化）

### 5. data-to-paper（Technion-Kishony-lab/data-to-paper）
- **Star**: 796
- **定位**: AI 自动化学术研究，从数据到论文的完整流程
- **考虑理由**: 多 agent 协作、backward-traceability（数值可追溯到代码行）、coding guardrails、rewind 机制
- **排除理由**: 创作场景相关度低（学术写作 vs 视觉创作），且社区规模较小

### 6. BigBanana-AI-Director（shuyu-labs/BigBanana-AI-Director）
- **Star**: 1.3k
- **定位**: AI 短剧导演平台（Script → Asset → Keyframe 工业化工作流）
- **考虑理由**: 角色一致性控制、场景连续性、分镜工作台、关键帧插值
- **排除理由**: 闭源产品（只有 Docker 部署，无源代码），无法拆解实现细节

---

## 最终推荐

### 推荐 #1: ComfyUI

**GitHub**: https://github.com/Comfy-Org/ComfyUI
**一句话**: 基于 DAG（有向无环图）的 diffusion model 执行引擎，用户通过连接节点构建任意复杂的图像/视频生成管线。

#### Harness 设计亮点

| 5 阶段框架 | ComfyUI 的对应设计 | 设计质量 |
|---|---|---|
| 1. 任务理解 + 工具就绪 | `DynamicPrompt` 解析用户构建的图、`validate_inputs` 预执行验证（类型检查、依赖检测、循环检测）、`NODE_CLASS_MAPPINGS` 工具注册表 | 优秀 |
| 2. 执行 + 分离评估 | `ExecutionList` 按拓扑序执行节点、`IsChangedCache` 判断哪些节点需要重新执行（评估与执行分离）、只执行图中变化的部分 | 优秀 |
| 3. 失败修复策略 | `ExecutionBlocker` 阻断传播机制、`handle_execution_error` 精确定位到具体节点和输入、`DependencyCycleError` / `NodeInputError` 分类错误、lazy evaluation 允许节点自主决定是否执行 | 优秀 |
| 4. Context 生命周期管理 | `CacheSet`（Classic/LRU/RAM Pressure 三种策略）、`HierarchicalCache` 按 prompt 生命周期管理、`DynamicPrompt` 支持运行时动态扩展图（ephemeral nodes）| 优秀 |
| 5. 监控 + 持续改进 | `ProgressEvent` 实时进度推送、`JobStatus` 状态跟踪（pending/in_progress/completed/failed/cancelled）、execution history 记录 | 良好 |

#### 核心架构洞察

1. **图即任务描述**: 用户构建的节点图就是 spec，执行引擎的职责是"忠实执行图的语义"。这比 prompt template 强大得多 — 任务描述是结构化的、可验证的、可缓存的。

2. **增量执行**: 通过 `IS_CHANGED` 机制 + input signature caching，系统只重新执行"变化了的子图"。这是 harness 的核心优化 — 不是每次从头来，而是精确定位需要重做的部分。

3. **验证前置**: `validate_prompt()` 在执行前做完整的类型检查、依赖检查、循环检测。harness 的第一层防线是"拒绝不合法的任务"。

4. **错误不吞并**: 错误精确到"哪个节点的哪个输入出了什么问题"，用户可以精确修复而不是猜测。

#### 跟动画场景的借鉴

- 动画生成可以建模为 DAG：脚本 → 分镜 → 角色设计 → 关键帧 → 中间帧 → 合成
- ComfyUI 的缓存策略直接可用：角色设计不变时，只重新生成关键帧
- `ExecutionBlocker` 思路可借鉴：当某帧质量不达标时，阻断下游合成，而不是继续执行
- 验证层的思路：动画 spec 也应该在执行前做可行性检查

---

### 推荐 #2: Pixelle-Video

**GitHub**: https://github.com/AIDC-AI/Pixelle-Video
**一句话**: AI 全自动短视频生成引擎，用 Template Method 模式编排"文案 → 视觉规划 → 逐帧生产 → 后期合成"的完整管线。

#### Harness 设计亮点

| 5 阶段框架 | Pixelle-Video 的对应设计 | 设计质量 |
|---|---|---|
| 1. 任务理解 + 工具就绪 | `PipelineContext` 统一状态容器、多 pipeline 变体（Standard/AssetBased/Custom）根据任务类型路由、参数验证和模板类型检测 | 良好 |
| 2. 执行 + 分离评估 | `FrameProcessor` 逐帧执行、`ImageAnalysisService` / `VideoAnalysisService` 独立的质量分析服务（评估与生成分离）| 良好 |
| 3. 失败修复策略 | `handle_exception` 异常捕获、try/except 包裹整个 pipeline lifecycle | 一般（有框架但不深入）|
| 4. Context 生命周期管理 | `PipelineContext` dataclass 贯穿全流程、`Storyboard` + `StoryboardFrame` 结构化中间状态、`PersistenceService` + `HistoryManager` 持久化和回溯 | 良好 |
| 5. 监控 + 持续改进 | `ProgressEvent` + `progress_callback` 实时进度、task 状态追踪（status/created_at/completed_at）| 良好 |

#### 核心架构洞察

1. **Template Method Pattern（模板方法）**: `LinearVideoPipeline` 定义了 8 个生命周期步骤（setup → content → title → visuals → storyboard → assets → post_production → finalize），子类只需 override 需要定制的步骤。这比"一个大函数"优雅得多 — 新的视频类型只需继承和替换几个方法。

2. **Context as First-Class Citizen**: `PipelineContext` 是贯穿所有步骤的状态载体，包含 input、task state、content、visuals、config、output。这解决了"多步骤间怎么传递状态"的问题。

3. **服务分层**: `PixelleVideoCore` 持有所有服务（llm/tts/media/video/image_analysis/video_analysis），pipeline 通过 `self.core` 访问。工具层和编排层清晰分离。

4. **分析服务的存在**: `ImageAnalysisService` 和 `VideoAnalysisService` 说明系统有"看生成结果"的能力，虽然当前未深度集成到自动反馈循环中，但架构已经为此留了位置。

#### 跟动画场景的借鉴

- **Pipeline 模式直接可用**: 动画项目完全可以继承 `LinearVideoPipeline` 的思路 — 定义动画的 lifecycle steps，子类实现具体逻辑
- **PipelineContext 模式**: 动画的中间状态（脚本、角色、场景、关键帧、中间帧）也需要一个统一容器贯穿全流程
- **FrameProcessor 逐帧编排**: 动画本质上也是逐帧/逐镜头处理，每帧经过 generate → compose → validate 的小管线
- **Asset-Based Pipeline 的变体思路**: 用户提供已有素材 → 分析 → 生成脚本 → 匹配 → 合成，这跟"给定角色设计 → 生成动画"的模式一致
- **分析服务预留**: 动画也需要"看生成结果是否合格"的能力（角色一致性检查、动作流畅度检查）

---

## 总结：创作类 Agent 的 Harness 设计跟通用 Agent 有什么不同

### 1. 任务描述是结构化的，不是自然语言

通用 agent 的任务通常是一句话 prompt。创作类 agent 的任务是**结构化 spec**：
- ComfyUI: 节点图（DAG）
- Pixelle-Video: Storyboard + StoryboardConfig
- BigBanana: Script → Character Sheet → Shot List

**设计含义**: 创作类 harness 需要一个"任务 schema"层，把模糊意图转化为可验证的结构化描述后再执行。

### 2. 中间产物有持久价值

通用 agent 的中间结果（思考链、工具调用）通常是临时的。创作类 agent 的中间产物（角色设计稿、分镜、关键帧）本身就有价值，用户需要**查看、编辑、复用**它们。

**设计含义**: 
- Context 管理不只是"传给下一步"，而是"持久化 + 可回溯 + 可编辑"
- ComfyUI 的方案：缓存中间结果，workflow 变化时只重新执行变化部分
- Pixelle-Video 的方案：PersistenceService + HistoryManager

### 3. 质量评估是主观的，需要人机协作

代码 agent 可以跑测试判断对错。创作类 agent 的"好坏"是主观的 — 画面好不好看、动画流不流畅。

**设计含义**:
- 不能完全自动闭环，需要在关键节点设置**人工审核点**
- 可以用 AI 做初步筛选（如 ImageAnalysisService），但最终判断留给人
- BigBanana 的"分镜工作台"思路：批量生成 → 展示给人选择 → 确认后继续

### 4. 失败粒度是"帧/镜头级"，不是"任务级"

代码 agent 失败了就是整个任务失败。创作类 agent 可能第 5 帧失败了，但前 4 帧是好的。

**设计含义**:
- 错误处理需要更细粒度：定位到具体帧/节点，而不是整个管线重来
- ComfyUI 的 `ExecutionBlocker` 正是这个思路 — 某个节点失败时阻断其下游，但不影响无关分支
- 动画项目应该支持"部分重做"：只重新生成失败的帧，保留成功的

### 5. 执行时间长，增量执行是刚需

创作类管线的执行时间通常是分钟到小时级。不可能每次修改都从头执行。

**设计含义**:
- 缓存策略是核心基础设施（ComfyUI 的 Classic/LRU/RAM Pressure 三级缓存）
- 变更检测（`IS_CHANGED`）决定了"需要重做什么"
- 动画项目：角色设计改了 → 所有包含该角色的帧需要重做；台词改了 → 只需重做对应帧的口型

---

## AI 生视频领域补充调研

> 调研日期：2026-05-26
> 调研目的：在"AI 生视频"这个更垂直的领域找到 harness 设计深度高的开源项目，补充 ComfyUI（通用 DAG 引擎）和 Pixelle-Video（线性管线）之外的视角。

---

### 候选项目列表

#### 1. Crayotter（idwts/Crayotter）⭐ 103
- **定位**: 多模态 AI 视频剪辑智能体，从文字需求到视频成品的端到端全自动生产
- **语言**: Python（LangGraph + OpenAI Tool Calling）
- **考虑理由**: 三阶段混合架构（Planner → Deep Research → ReAct Agent）+ RL 训练阶段 + 经验记忆系统 + 奖励函数设计 + 事件驱动运行时
- **结论**: **最终推荐 #1** — harness 设计最深的视频 agent，覆盖全部 5 个阶段

#### 2. Jellyfish（Forget-C/Jellyfish）⭐ 3.5k
- **定位**: AI 短剧端到端生产工作空间（剧本 → 分镜 → 一致性管理 → 镜头准备 → 视频生成 → 导出）
- **语言**: Python（FastAPI + Celery + SQLAlchemy + LangChain）
- **考虑理由**: 工业级任务生命周期管理（TaskExecutor + TaskRegistry + TaskStore）、多种专职 Agent（一致性检查、角色画像分析、道具分析等）、策略模式交付（Streaming/AsyncPolling）、Celery Worker 架构
- **结论**: **最终推荐 #2** — 最佳工业级 harness 参照物，任务管理设计最成熟

#### 3. ViMax（HKUDS/ViMax）⭐ 7.5k
- **定位**: Agentic Video Generation（Director + Screenwriter + Producer + Generator 多角色协作）
- **语言**: Python（LangChain + Pydantic + tenacity + asyncio）
- **考虑理由**: 清晰的 multi-agent 分工（12 种 agent）、质量评估组件（BestImageSelector 用 VLM 选最优图）、相机树构建和帧事件同步、retry with tenacity
- **排除理由**: harness 设计停留在"retry + 多 agent 串联"层面，没有任务生命周期管理、没有经验积累、没有 RL 反馈。架构值得参考但 harness 深度不如 Crayotter 和 Jellyfish

#### 4. Code2Video（showlab/Code2Video）⭐ 1.8k — ICML 2026
- **定位**: 通过 Manim 代码生成教学视频（LLM → Code → Render → VLM Feedback → Fix）
- **语言**: Python
- **考虑理由**: 完整的 generate-render-evaluate-fix 闭环、MLLM 视觉反馈循环（拍视频 → VLM 看视频 → 给修改建议 → 重新生成代码）、多层 retry（outline/storyboard/code/fix/feedback 各层都有独立重试上限）、并行渲染
- **排除理由**: 偏研究代码风格（单文件 agent.py），没有任务管理、没有持久化、没有运行时事件系统。但其"视觉反馈循环"设计可单独借鉴

#### 5. Toonflow（HBAI-Ltd/Toonflow-app）⭐ 8.7k
- **定位**: 一站式 AI 短剧创作桌面端（小说/剧本 → 分镜 → 角色 → 视频）
- **语言**: TypeScript（Electron + Node.js + AI SDK）
- **考虑理由**: 有 Agent Memory（短期/长期/RAG）、决策 Agent + 子 Agent 派生、技能文件驱动行为
- **排除理由**: 架构偏前端应用（Socket.io + Express），harness 层面的深度（任务管理、失败处理、质量评估）不及 Crayotter 和 Jellyfish。Memory 设计可参考

#### 6. Paper2Video（showlab/Paper2Video）⭐ 2.3k
- **定位**: 学术论文自动转演讲视频（PDF → Slides → TTS → Talking Head → 合成）
- **语言**: Python
- **考虑理由**: 有 PresentArena 质量评估（VLM 做 A/B 比较）、tree-search 布局优化（生成多候选 → VLM 选最佳）、MetaSim 内容/音频评估
- **排除理由**: 管线是简单的串行脚本（没有任务抽象、没有状态管理、没有错误恢复策略），harness 设计接近零。但其"VLM 做裁判 + tree search"思路值得借鉴

#### 7. manim-agent（cordonarson-gif/manim-agent）⭐ 1
- **定位**: LangGraph 多 agent 系统，用于规划、生成、渲染、视觉审查 Manim 动画
- **语言**: Python（LangGraph）
- **考虑理由**: 极其清晰的 harness 设计 — Planner → Coder → AST Review → Execution → Vision Critic 五节点图，有结构化失败分类（content_failure/infra_failure）、严重度分级（low/medium/high）、MAX_RETRIES 硬停、infra vs content 故障区分路由
- **排除理由**: 仅 1 star，代码量小。但其 harness 设计 pattern 非常干净，是学习"分离评估 + 失败修复策略"的最佳微型样本

---

### 最终推荐

---

### 推荐 #1: Crayotter

**GitHub**: https://github.com/idwts/Crayotter
**一句话**: 基于 LangGraph 的多模态视频剪辑智能体，用三阶段混合架构（规划 → 深度研究 → 自主创作）完成从文字需求到视频成品的全自动生产，并通过 RL 训练不断提升 agent 的工具使用能力。

#### 为什么推荐它（而不是 star 更高的 ViMax/Toonflow）

ViMax 和 Toonflow 的 star 多，但 harness 设计停留在"多 agent 串联 + retry"层面。Crayotter 的独特之处在于它不只解决"怎么执行"，还解决了"怎么变得更好"（RL 训练 + 经验记忆）和"长任务怎么管理"（事件总线 + 任务超时 + 取消机制）。

#### Harness 设计亮点（对应 5 阶段框架）

| 5 阶段框架 | Crayotter 的对应设计 | 设计质量 |
|---|---|---|
| 1. 任务理解 + 工具就绪 | `AgentState` 结构化状态（含 user_request、plan、target_duration）、`tool_catalog.py` 工具注册表、Phase 1 的 `Plan` + `Step` 结构化任务分解 | 优秀 |
| 2. 执行 + 分离评估 | Phase 1（Plan-Execute 确保可靠执行）→ Phase 2（纯推理生成剪辑蓝图，不调工具）→ Phase 3（ReAct 自主创作）。Phase 2 是"分离评估"的典范 — 纯思考、产出结构化蓝图供 Phase 3 执行 | 优秀 |
| 3. 失败修复策略 | `reward.py` 的 step-level 奖励惩罚（工具成功/失败、重复调用惩罚、顺序奖励）+ episode-level 奖励（时长偏差、效率惩罚）；`AGENT_STALL_TIMEOUT_SECONDS` 超时熔断；`cancel_requested` 主动中止 | 优秀 |
| 4. Context 生命周期管理 | `memory_reference.py` 经验记忆系统（Reusable Tool Patterns / Workflow Patterns / Failure Guards / Quick Checklist）、`INJECTION_MEMORY_CHAR_LIMIT` 控制注入量、`Reference Boundary` 声明当前任务优先于历史经验 | 极优秀 |
| 5. 监控 + 持续改进 | `EventBus` 实时事件推送 + `events.jsonl` 持久化轨迹、`_log_react_tool_trace` Phase 3 工具轨迹日志、RL 训练循环（GRPO）用 `compute_episode_reward` 反哺策略 | 极优秀 |

#### 核心架构洞察

1. **三阶段设计解决了"何时用确定性、何时用自主性"的问题**:
   - Phase 1（素材准备）: 步骤可预见，用 Plan-and-Execute 确保每步都做到
   - Phase 2（剪辑研究）: 需要深度思考，用纯推理（不调工具）生成结构化蓝图
   - Phase 3（自主创作）: 需要灵活应变，用 ReAct Agent + 完整工具集自主执行
   - 这解决了"agent 太自由会乱来、太受限做不出好东西"的矛盾

2. **经验记忆系统 = 持续改进的基础设施**:
   - 每次任务完成后提炼出抽象的可复用模式（而非具体任务细节）
   - 分类存储：工具用法 / 流程模式 / 失败防护 / 检查清单
   - 注入时有边界声明："当前素材分析与历史案例结论不同，必须以当前素材分析为准"
   - 这防止了"经验污染当前判断"的问题

3. **RL 训练闭环 = harness 的终极形态**:
   - 不是人工调参数，而是让 agent 通过大量 episode 自己学会"什么时候该用什么工具、以什么顺序"
   - 奖励函数精确定义了"好的行为"：工具成功 +0.6、重复调用 -0.2、先检查再导出 +0.15、先验证再旁白 +0.2
   - 这是从"规则驱动"到"学习驱动"的进化

4. **事件驱动运行时 = 可观测性的基础**:
   - `EventBus` 让所有行为都可追踪
   - `events.jsonl` 让每次任务都可复盘
   - `RuntimeManager` 管理任务生命周期（create → running → cancelled/done）
   - 支持 stall 超时检测（agent 卡住了能发现）

#### 拆解入口（源码文件路径）

| 要学什么 | 看哪个文件 |
|---|---|
| 三阶段架构全貌 | `script/graph.py` — 状态定义、Phase 路由、工具分组 |
| 经验记忆系统 | `script/memory_reference.py` — 记忆解析、注入、边界控制 |
| RL 奖励设计 | `phase3_rl/reward.py` — step/episode 双层奖励函数 |
| 策略抽象（可替换 LLM） | `phase3_rl/policies.py` — ScriptedPolicy / OpenAIToolPolicy |
| Agent Loop（RL 训练） | `phase3_rl/verl_agent_loop.py` — verl 框架集成 |
| 工具注册表 | `phase3_rl/tool_catalog.py` + `script/tools/` 目录 |
| 运行时管理 | `app/backend/runtime_manager.py` — 任务创建/取消/超时 |
| 事件系统 | `app/backend/event_bus.py` — 实时事件发布/订阅 |

---

### 推荐 #2: Jellyfish

**GitHub**: https://github.com/Forget-C/Jellyfish
**一句话**: AI 短剧端到端生产工作空间，用工业级任务管理系统（Celery + TaskExecutor + TaskRegistry）编排从剧本解析到视频生成的完整流程，每个环节由专职 Agent 执行。

#### 为什么推荐它（而不是 Crayotter 之外的其他项目）

Jellyfish 补充了 Crayotter 缺少的维度：**工业级任务编排**。Crayotter 擅长"单 agent 怎么做得更好"，Jellyfish 擅长"多任务怎么可靠地并行执行"。对动画项目来说两者都需要。

#### Harness 设计亮点（对应 5 阶段框架）

| 5 阶段框架 | Jellyfish 的对应设计 | 设计质量 |
|---|---|---|
| 1. 任务理解 + 工具就绪 | `TaskExecutorRegistry` 按 task_kind 路由到具体 Executor、`AgentBase` 固化 PromptTemplate + OutputModel + JSON 解析容错、`AbstractLLMResultGenerator` 统一 LLM 调用接口 | 优秀 |
| 2. 执行 + 分离评估 | `ConsistencyCheckerAgent` 独立于生产 Agent 做一致性检查（角色混淆检测）、`ScriptOptimizerAgent` 基于一致性检查结果优化剧本 — 分析和生产明确分离 | 优秀 |
| 3. 失败修复策略 | `AbstractWorkerTaskExecutor.run()` 三段式生命周期（mark_running → execute → apply_and_finish）任一阶段失败都精确标记 + cancel 检查穿插每个阶段；`_ensure_not_timed_out` 超时保护；JSON 解析的 6 层降级容错（json.loads → repair → ast.literal_eval → kwargs parse） | 优秀 |
| 4. Context 生命周期管理 | `TaskRecord` 统一任务表示（status/progress/payload/result/error/timing）、`SyncSqlAlchemyTaskStore` 持久化到数据库、`DeliveryStrategy` 分离结果交付方式（streaming/polling） | 优秀 |
| 5. 监控 + 持续改进 | `task_logging.py` 任务事件记录（started/cancelled/succeeded/failed + elapsed_ms）、`script_extraction_cache.py` 结果缓存避免重复计算 | 良好 |

#### 核心架构洞察

1. **TaskExecutor 模板方法 = 可靠执行的保障**:
   - `run()` 方法定义了固定的生命周期：load_args → execute → apply_result
   - 每个阶段之间都检查 cancel 和 timeout
   - 子类只需实现 `execute()` 和 `apply_result()`，不用操心"何时标 running、何时标 failed"
   - 这消除了"忘记处理边界情况"的问题

2. **AgentBase 的 JSON 解析容错链 = 真实世界的 LLM 输出处理**:
   - LLM 输出格式不可靠是工程中的真实痛点
   - 6 层降级：标准 json.loads → 提取 markdown 代码块 → 修复尾逗号/引号 → Python literal_eval → kwargs 解析 → 提取第一个 JSON 对象
   - 这不是过度设计，是面对现实的 robustness

3. **TaskRegistry = 统一调度的入口**:
   - 所有任务类型（script_divide / script_extract / video_generation / image_generation / shot_frame_prompt）注册到同一个 registry
   - 新增任务类型只需：写一个 Executor 子类 + register 一行
   - 超时时间按任务类型差异化设置（script 900s / video 3600s / image 1800s）

4. **一致性检查 = 创作类 agent 特有的质量网关**:
   - `ConsistencyCheckerAgent` 检测"同一角色在不同段落身份矛盾"
   - `ScriptOptimizerAgent` 接收一致性检查结果后修复剧本
   - 这是创作管线特有的模式：不是"代码跑不跑得通"，而是"内容逻辑通不通"

#### 拆解入口（源码文件路径）

| 要学什么 | 看哪个文件 |
|---|---|
| 任务执行器模板 | `backend/app/services/worker/task_executor.py` — AbstractWorkerTaskExecutor |
| 任务注册表 | `backend/app/services/worker/task_registry.py` — 全部 task_kind 一览 |
| Agent 基类（含 JSON 容错） | `backend/app/chains/agents/base.py` — 解析链 |
| 一致性检查 Agent | `backend/app/chains/agents/consistency_checker_agent.py` |
| 任务状态管理 | `backend/app/core/task_manager/types.py` — TaskRecord / TaskStatus |
| 交付策略 | `backend/app/core/task_manager/strategies.py` — Streaming / AsyncPolling |
| 脚本处理 Worker | `backend/app/services/script_processing_worker.py` — 各 Executor 实现 |
| 镜头帧 Prompt Agent | `backend/app/chains/agents/shot_frame_prompt_agents.py` |

---

### 值得额外借鉴的设计（来自未推荐项目）

#### Code2Video 的「视觉反馈循环」

```
生成代码 → 渲染视频 → VLM 看视频 → 结构化反馈（severity + issues + fix）→ 修改代码 → 重新渲染
```

关键设计：
- 反馈是结构化的（有 severity、有具体 problem 和 solution），不是模糊的"不好看"
- 反馈轮数可配置（`feedback_rounds = 2`），避免无限循环
- 每轮反馈修改有独立重试上限（`max_feedback_gen_code_tries = 3`）
- 修改失败会回退到上一个能工作的版本

**对动画项目的启示**: 生成关键帧 → VLM 审查一致性/质量 → 结构化反馈 → 精确修复，而不是盲目重新生成。

#### manim-agent 的「故障分类路由」

```python
FailureType = Literal["content", "infra", "unknown"]
# content failure → 重新生成代码
# infra failure → 不重试（Docker 问题、环境问题）
# unknown → 有限重试
```

关键设计：
- 区分"内容不对"和"基础设施坏了"，避免对 infra 问题做无意义的内容重试
- `vision_severity` 分 low/medium/high，low 直接通过，不浪费资源
- `force_finish` 硬停机制防止无限循环

**对动画项目的启示**: 模型生成质量差（content）→ 换 prompt/重试；API 超时（infra）→ 等待或切换 provider；角色一致性差（content）→ 加 reference image。不同类型的失败需要不同的修复策略。

---

### 对比总结

| 维度 | Crayotter | Jellyfish | 互补关系 |
|---|---|---|---|
| 定位 | 单任务深度执行 | 多任务并行编排 | Crayotter 教你"一个视频怎么做好"，Jellyfish 教你"一批视频怎么可靠地做完" |
| 核心 harness 思想 | 三阶段混合 + RL 训练 + 经验记忆 | 任务模板 + 注册表 + 持久化 | 一个强在"自我进化"，一个强在"工业可靠性" |
| 最大亮点 | 经验记忆 + RL 奖励函数 | TaskExecutor 生命周期 + JSON 容错 | — |
| 最大短板 | star 少（103），可能不够稳定 | 没有自我改进机制（第 5 阶段偏弱） | — |
| 对动画项目价值 | Phase 2 的"纯推理出蓝图"思路、经验记忆系统 | 任务管理框架可直接复用、一致性检查思路 | — |
| 技术栈 | LangGraph + OpenAI + verl | FastAPI + Celery + SQLAlchemy + LangChain | — |
