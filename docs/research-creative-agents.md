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
