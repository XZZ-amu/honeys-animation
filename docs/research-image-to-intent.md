# 从参考图/GIF 提取视觉意图：模型与方案调研

> 调研日期：2026-05-29
> 调研目的：找到能从动画 GIF / 参考图中精准提取"视觉意图要素"（不只是描述内容，而是提取实现方式）的模型和方案
> 核心场景：用户给一张 GIF → 系统提取运动方式、物理行为、时间结构 → 用代码复刻

---

## 核心难题精确定义

### 难题 1：视觉描述的"抽象层级错位"

**定义**：通用 VLM 被训练做"语义描述"（图里有什么），而我们需要的是"实现描述"（这个效果是怎么做的）。

**为什么难**：
- "碎片飞走" vs "从迎风侧逐像素脱落、速度 decay 0.95、方向带 ±15° 随机偏移" — 前者是语义，后者是实现
- 所有 image captioning 模型的训练数据都是语义级别的标注（COCO、Visual Genome），没有"动画实现参数"的数据集
- 这不是模型能力的问题，是训练数据的缺失

### 难题 2：GIF 的时间信息丢失

**定义**：GIF 是逐帧的位图序列，但动画的本质是"参数随时间的变化函数"。从离散帧反推连续函数是病态问题（ill-posed）。

**为什么难**：
- 30fps 的 GIF 里每帧之间的位移可能只有 2-3px，模型很难从中推断"这是 ease-out 还是 linear"
- 缓动曲线的差异在视觉上极其微妙（人需要慢放才能分辨）
- 多个元素同时运动时，模型容易只描述最显著的那个

### 难题 3：从"视觉现象"到"代码原语"的映射

**定义**：模型能看到"粒子散开了"，但不知道这对应 `particles.forEach(p => p.velocity += gravity * dt)` 还是 CSS `animation: scatter 0.5s ease-out`。

**为什么难**：
- 同一个视觉效果可以有完全不同的实现方式
- 模型需要同时理解"视觉"和"代码生成方式"——这是跨域知识
- 没有现成的"视觉效果 → 代码实现"对齐训练数据

---

## 成熟解法一览

### 方案 A：通用 VLM + 定制 Prompt（当前做法的强化版）

#### 代表模型

| 模型 | 来源 | 参数量 | 多帧能力 | 结构化输出 | 可用方式 |
|------|------|--------|---------|-----------|---------|
| GPT-4o | OpenAI | 未公开 | 支持多图输入（逐帧喂入） | 支持 JSON mode | API |
| Claude 3.5/4 Sonnet | Anthropic | 未公开 | 支持多图输入 | 支持 structured output | API |
| Gemini 2.0 Flash/Pro | Google | 未公开 | 原生视频输入（最强） | 支持 JSON | API |
| Qwen2.5-VL-72B | 阿里 | 72B | 支持视频输入 | 通过 prompt 约束 | HuggingFace / API |
| InternVL2.5-78B | 上海 AI Lab | 78B | 支持多帧 | 通过 prompt 约束 | HuggingFace |
| LLaVA-OneVision-72B | 社区 | 72B | 支持视频 | 通过 prompt 约束 | HuggingFace |
| CogVLM2-Video | 智谱 | 13B+ | 原生视频理解 | 通过 prompt 约束 | HuggingFace |

#### 核心思路

不换模型，而是**重新设计提取 prompt 的结构**，把"自由描述"变成"按维度填表"：

```
你是一个动画技术分析师。分析这个 GIF 的每一帧，输出以下结构化信息：

1. 视觉元素清单（形状、颜色、初始位置、大小）
2. 每个元素的运动轨迹类型（线性/弧线/弹跳/随机）
3. 运动参数估算（速度变化趋势：加速/减速/匀速/先快后慢）
4. 元素间关系（独立运动/跟随/碰撞/弹性连接）
5. 时间线（第 1-10 帧发生什么、第 11-20 帧发生什么...）
6. 最接近的动画原语（从以下选项中选：bounce / ease-out / overshoot / spring / inertia / sand-erosion / wiggle / sway / path-follow）

输出格式为 JSON。
```

#### Tradeoff

| 优势 | 代价 |
|------|------|
| 零部署成本，立即可用 | 依赖模型的"动画知识"——模型可能不知道 ease-out 和 spring 的视觉差异 |
| 结构化 prompt 大幅减少遗漏 | 帧间微妙差异仍然容易被忽略（2px 位移差异看不出是什么曲线） |
| 可以逐步迭代 prompt | 对复杂组合动画（多元素 + 多阶段）描述质量下降 |
| Gemini 2.0 原生视频输入最强 | API 成本高（多帧 = 多 token） |

---

### 方案 B：帧差分析 + 光流提取（计算机视觉经典方法）

#### 代表工具/库

| 工具 | 用途 | 可用方式 |
|------|------|---------|
| OpenCV Optical Flow（Farneback / Lucas-Kanade） | 逐帧运动向量 | pip install opencv-python |
| RAFT（Recurrent All-Pairs Field Transforms） | 高精度光流 | HuggingFace / GitHub |
| CoTracker（Meta） | 多点长程追踪 | HuggingFace / pip |
| SAM2（Segment Anything 2） | 视频中分割追踪每个元素 | HuggingFace |
| DEVA（Tracking Anything） | 元素分割 + 追踪 | GitHub |

#### 核心思路

不让模型"看"动画，而是用 CV 工具**先把动画拆解成数据**，再让模型分析数据：

```
GIF → 逐帧拆解
  → 帧差分析（哪些像素在动）
  → 光流计算（每个像素的运动方向和速度）
  → 元素追踪（CoTracker 追踪关键点轨迹）
  → 轨迹数据（x,y 坐标序列）
  → 曲线拟合（判断是 ease-out / spring / linear）
  → 结构化输出
```

**关键步骤：轨迹 → 缓动曲线判断**

拿到元素的 (x, y, t) 轨迹后，可以计算：
- 速度序列：`v[i] = distance(pos[i+1], pos[i]) / dt`
- 加速度：`a[i] = v[i+1] - v[i]`
- 曲线拟合：把速度曲线跟已知缓动函数（ease-out、spring、bounce）做最小二乘拟合，找最匹配的

#### Tradeoff

| 优势 | 代价 |
|------|------|
| 精确的数值数据（像素级位移、真实速度） | 需要额外的计算管线（Python 环境 + CV 库） |
| 能区分肉眼难辨的缓动差异 | 对"形变"类动画（sand-erosion、morph）效果差——形变不是"位移" |
| 不依赖模型的"动画知识" | GIF 压缩和低帧率会引入噪声 |
| 可以精确提取运动参数 | 管线复杂度高，需要维护 |

---

### 方案 C：VLM + 视频专用模型的多帧深度分析

#### 代表模型

| 模型 | 特点 | 参数量 | 可用方式 |
|------|------|--------|---------|
| Qwen2.5-VL（视频模式） | 原生视频输入，支持动态帧采样 | 7B-72B | HuggingFace / DashScope API |
| Gemini 2.0 Flash | 原生视频，支持长视频（1hr+），时间定位能力强 | 未公开 | Google AI Studio API |
| InternVL2.5-Video | 视频理解，支持 temporal grounding | 8B-78B | HuggingFace |
| VideoLLaMA3 | 视频+音频多模态，时间精确理解 | 7B-72B | HuggingFace |
| LLaVA-Video | 专为视频设计的指令跟随 | 7B-72B | HuggingFace |
| TimeSformer / VideoMAE v2 | 视频分类/动作识别骨干 | 较小 | HuggingFace |

#### 核心思路

利用视频理解模型的**时间感知能力**，直接分析动画的时间结构：

```
GIF → 视频模型（Gemini 2.0 / Qwen2.5-VL）
  → 多帧对比分析
  → prompt 引导输出：
    "对比第 1 帧和第 5 帧，元素 A 的位置变化了多少？速度是加快还是减慢？"
    "这个动画分几个阶段？每个阶段的主要变化是什么？"
```

**Gemini 2.0 的优势**：Google 的模型在视频理解上有独特优势——原生处理视频帧，不需要手动拆帧。可以问它"这个动画从第 0.5s 到 1.0s 发生了什么变化"。

**Qwen2.5-VL 的优势**：开源可自部署，视频模式支持动态分辨率和动态帧采样，对短视频/GIF 的理解能力在开源模型中最强。

#### Tradeoff

| 优势 | 代价 |
|------|------|
| 原生理解时间维度，不需要手动拆帧 | 仍然是"感知"而非"精确测量"——参数估算有误差 |
| 能理解"阶段性变化"（先快后慢、先聚后散） | 开源模型 72B 需要 GPU 部署（A100 80G 起步） |
| Gemini 2.0 Flash 性价比极高 | 对"微妙缓动差异"的区分能力仍然有限 |
| 可以用自然语言问具体问题 | 不如方案 B 的数值精确 |

---

### 方案 D：多阶段管线（推荐方案）

#### 核心思路：分层提取，逐层精确

```
┌─────────────────────────────────────────────────┐
│ Layer 1: 元素识别与分割                           │
│ 工具: SAM2 / 帧差分析                            │
│ 输出: 每个运动元素的 mask + ID                    │
├─────────────────────────────────────────────────┤
│ Layer 2: 轨迹提取                                │
│ 工具: CoTracker / 光流                           │
│ 输出: 每个元素的 (x, y, scale, rotation) 序列     │
├─────────────────────────────────────────────────┤
│ Layer 3: 参数拟合                                │
│ 工具: 数学拟合（scipy curve_fit）                 │
│ 输出: 缓动类型 + 参数（如 spring: stiffness=200） │
├─────────────────────────────────────────────────┤
│ Layer 4: 语义理解（VLM）                          │
│ 工具: Claude/GPT-4o/Gemini                       │
│ 输入: 原始 GIF + Layer 1-3 的数据                │
│ 输出: 动画意图的完整结构化描述                     │
└─────────────────────────────────────────────────┘
```

#### 各层详解

**Layer 1 — 元素识别**

目标：知道"画面里有几个独立运动的东西"

- 简单情况（纯色几何形状）：帧差 + 连通域分析即可
- 复杂情况（有重叠、有形变）：用 SAM2 做视频分割

对我们的场景：动画风格是"干净、锐利、几何"，元素之间对比度高，**帧差分析大概率够用**，不需要 SAM2。

**Layer 2 — 轨迹提取**

目标：知道"每个东西怎么动的"

- CoTracker：在每个元素上放追踪点，输出完整轨迹
- 对简单位移：质心追踪即可
- 对形变（sand-erosion）：需要多点追踪，观察"哪些点先动、哪些后动"

输出示例：
```json
{
  "element_A": {
    "trajectory": [[100, 200], [105, 198], [112, 195], ...],
    "scale": [1.0, 1.02, 1.05, 1.03, 1.0, ...],
    "rotation": [0, 0, 2, 5, 8, ...]
  }
}
```

**Layer 3 — 参数拟合**

目标：从轨迹数据判断"这是什么类型的运动"

核心算法：
```python
# 位移序列 → 速度序列
velocities = np.diff(positions) / dt

# 尝试拟合各种缓动模型
models = {
    "ease_out": lambda t, v0: v0 * (1 - t)**2,
    "spring": lambda t, A, k, d: A * np.exp(-d*t) * np.cos(k*t),
    "bounce": bounce_function,
    "linear": lambda t, v: v * t,
}

best_fit = min(models, key=lambda m: residual(m, velocities))
```

这一层的输出直接对应我们的 `motion-presets.md` 里的动画原语。

**Layer 4 — VLM 语义整合**

目标：把数据变成"动画意图描述"

给 VLM 的输入不再只是图片，而是：
- 原始 GIF（让它看整体感觉）
- Layer 1 的元素清单
- Layer 2 的轨迹数据
- Layer 3 的拟合结果

让 VLM 做的事变成：
- 确认/修正拟合结果（"这个看起来更像 bounce 还是 spring？"）
- 补充语义信息（"这些粒子是从中心爆发的，像爆炸"）
- 描述元素间关系（"A 推动了 B"）
- 映射到我们的动画原语体系

#### Tradeoff

| 优势 | 代价 |
|------|------|
| 数值精确（CV 层）+ 语义丰富（VLM 层）互补 | 管线复杂度最高，开发维护成本大 |
| 每一层独立可测试可调试 | 端到端延迟高（需要跑完整条管线） |
| VLM 的工作从"凭空猜测"变成"确认数据" | 对 GIF 质量有要求（低帧率/高压缩会影响 CV 层） |
| 直接输出参数，可用于代码生成 | 对"形变"类效果的处理仍然是难点 |

---

### 方案 E：动作/动效分类模型（轻量补充）

#### 代表模型

| 模型 | 用途 | 可用方式 |
|------|------|---------|
| VideoMAE v2 | 视频分类/动作识别 | HuggingFace |
| TimeSformer | 时间注意力视频分类 | HuggingFace |
| X-CLIP | 文本-视频对齐 | HuggingFace |

#### 核心思路

不做"开放式描述"，而是做"分类"——把动画效果归类到预定义的类型中：

```
GIF → 分类模型 → "这是 particle_burst 类型的动画"
                → "运动模式最接近 ease-out + radial"
                → "复杂度级别：中"
```

**关键前提**：需要自己构建分类体系和训练数据。把 `motion-presets.md` 里定义的动画原语作为分类标签，收集/生成对应的 GIF 样本做 fine-tune。

#### Tradeoff

| 优势 | 代价 |
|------|------|
| 推理快（分类比生成描述快 10 倍） | 需要构建训练数据（至少每类 50-100 个样本） |
| 输出直接对应我们的原语体系 | 不能处理训练集之外的新动画类型 |
| 模型小，可本地跑（甚至手机端） | 只给"类型"不给"参数"——仍需配合其他方案 |

---

## 现有模型在"动画理解"上的实际能力评估

### 经过验证的事实

| 模型 | 能做到 | 做不到 |
|------|--------|--------|
| GPT-4o | 识别动画类型（"这是粒子爆发"）、描述大致运动方向、理解时间顺序 | 精确区分缓动类型、估算速度参数、描述复杂的多元素同步关系 |
| Claude 3.5 Sonnet (Vision) | 结构化描述能力强（给 JSON schema 能填）、理解空间关系、对设计稿的理解较好 | 对运动的"快慢"判断不准、容易简化复杂形变、多帧对比能力弱 |
| Gemini 2.0 Flash | 视频原生输入、时间定位准确、能描述"先后发生了什么" | 参数估算仍然是定性（"快/慢"）而非定量 |
| Qwen2.5-VL-72B | 开源最强视频理解、中文描述细腻 | 72B 部署门槛高、结构化输出需要 fine-tune |
| InternVL2.5 | 中文理解强、多图对比能力好 | 视频理解略弱于 Qwen2.5-VL |

### 关键结论

**没有任何现有模型能直接从 GIF 输出可用于代码生成的动画参数。**

所有 VLM 的能力上限是：
- 定性描述：能说"从中心向外散开，速度先快后慢"
- 类型识别：能说"这是粒子效果"
- 时间结构：能说"先出现字母，然后爆发粒子，最后粒子消散"

不能做到的：
- 定量参数：不能说 "initialVelocity: 8px/frame, decay: 0.92, angle: random(0, 360)"
- 缓动精确匹配：不能说"这是 cubic-bezier(0.25, 0.1, 0.25, 1.0)"
- 物理模型识别：不能说"这用了 Verlet 积分 + 弹簧约束"

---

## 推荐方案：对我们场景的具体建议

### 短期（立即可做）：强化 Prompt + 多帧输入

**改造方向**：不换模型，重构提取流程

1. **GIF 拆帧策略**：
   - 关键帧采样（首帧、峰值帧、末帧 + 等间距中间帧）
   - 建议 8-12 帧输入，太多 token 成本高且信息冗余

2. **分步 Prompt 替代一次性描述**：

```
Step 1（元素识别）:
"列出这个动画中所有独立运动的视觉元素。对每个元素描述：形状、颜色、初始位置、大小。"

Step 2（运动分析——逐帧对比）:
"对比第 1 帧和第 4 帧，元素 A 的位置变化了多少？方向是什么？
 对比第 4 帧和第 8 帧，速度是加快了还是减慢了？"

Step 3（模式匹配）:
"根据以上观察，这个元素的运动最接近以下哪种模式？
 A. ease-out（先快后慢，减速停下）
 B. spring（弹性过冲，来回摆动后归位）
 C. bounce（着地反弹，每次弹跳越来越小）
 D. linear（匀速）
 E. inertia（被推出后因摩擦力慢慢停下）
 选一个并解释为什么。"

Step 4（时间结构）:
"这个动画分几个阶段？按时间顺序列出每个阶段发生了什么。"

Step 5（映射到 spec）:
"基于以上分析，填充以下 JSON 结构：
{
  elements: [{shape, color, size, initialPosition}],
  motionType: 'bounce|ease-out|spring|...',
  direction: 'radial|linear|arc|random',
  speedProfile: 'fast-to-slow|slow-to-fast|constant|oscillating',
  phases: [{startFrame, endFrame, description}],
  physicsHints: {hasGravity, hasElasticity, hasFriction}
}"
```

3. **选用 Gemini 2.0 Flash 做视频分析**（原生视频输入 + 性价比最高），Claude/GPT-4o 做最终的 spec 整合。

**预期效果**：从"经常丢失关键信息"提升到"80% 场景下能提取到正确的动画类型和大致参数"。

**成本**：几乎为零（只改 prompt），效果提升显著。

---

### 中期（1-2 周）：加入 CV 轨迹提取层

**改造方向**：在 VLM 之前加一层数据提取

1. **工具选择**：
   - 帧差分析 + 质心追踪（我们的动画风格简洁、元素对比度高，这个够用）
   - 不需要上 SAM2 / CoTracker 这种重型工具

2. **实现方式**（Python 脚本，几十行）：

```python
import cv2
import numpy as np
from PIL import Image

def extract_motion_data(gif_path):
    """从 GIF 提取运动数据"""
    frames = load_gif_frames(gif_path)
    
    # 1. 帧差 → 找到运动区域
    motion_masks = [frame_diff(frames[i], frames[i+1]) for i in range(len(frames)-1)]
    
    # 2. 连通域 → 识别独立元素
    elements = identify_elements(motion_masks[0], frames[0])
    
    # 3. 逐帧追踪质心 → 轨迹
    trajectories = track_centroids(elements, frames)
    
    # 4. 轨迹 → 速度 → 缓动类型判断
    for elem_id, traj in trajectories.items():
        velocities = np.diff(traj, axis=0)
        speeds = np.linalg.norm(velocities, axis=1)
        easing_type = classify_easing(speeds)  # 与预定义曲线做匹配
        
    return {
        "elements": elements,
        "trajectories": trajectories,
        "easing_types": easing_types,
        "speed_profiles": speed_profiles
    }
```

3. **集成方式**：CV 提取结果作为"辅助数据"喂给 VLM，VLM 从"看图猜"变成"看图 + 看数据确认"。

**预期效果**：缓动类型判断准确率从 ~50% 提升到 ~85%。速度/方向参数有数值依据。

**成本**：开发 2-3 天，依赖 opencv-python + numpy + scipy。

---

### 长期（可选）：自定义分类模型

如果动画项目量产化，且动画类型相对固定（都在 motion-presets.md 定义的范围内），可以：

1. 用现有动画生成 200-500 个带标签的 GIF 样本
2. Fine-tune 一个轻量视频分类模型（VideoMAE-small，22M 参数）
3. 输入 GIF → 直接输出动画类型 + 置信度

**但这不是当前优先级。** 短期和中期方案已经能解决 90% 的问题。

---

## 具体使用方式

### Gemini 2.0 Flash — 视频原生分析

```python
import google.generativeai as genai

genai.configure(api_key="YOUR_KEY")
model = genai.GenerativeModel("gemini-2.0-flash")

# 直接上传 GIF 作为视频
video_file = genai.upload_file("animation.gif")

response = model.generate_content([
    video_file,
    """分析这个动画，输出 JSON 格式：
    {
      "elements": [{"id": "A", "shape": "...", "color": "...", "role": "主体/装饰/背景"}],
      "phases": [{"time": "0-0.3s", "event": "..."}],
      "motionType": "bounce|ease-out|spring|particle-burst|...",
      "direction": "radial|linear-down|arc|...",
      "speedProfile": "fast-to-slow|oscillating|...",
      "easing": "ease-out|spring|bounce|...",
      "physicsHints": {"gravity": true/false, "elasticity": true/false, "friction": true/false}
    }"""
])
```

**价格**：Gemini 2.0 Flash 极便宜（视频约 $0.02/分钟），适合高频调用。

### Qwen2.5-VL — 开源本地部署

```python
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

model = Qwen2VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-7B-Instruct",  # 7B 版本可在 RTX 4090 上跑
    torch_dtype="auto",
    device_map="auto"
)
processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-7B-Instruct")

# 支持直接传入视频文件
messages = [{
    "role": "user",
    "content": [
        {"type": "video", "video": "animation.gif", "fps": 2},  # 动态采样
        {"type": "text", "text": "分析这个动画的运动方式..."}
    ]
}]
```

**部署要求**：7B 版本需 16GB+ VRAM，72B 版本需 80GB+（或量化后 2x 24GB）。

### OpenCV 轨迹提取（中期方案核心）

```python
import cv2
import numpy as np
from scipy.optimize import curve_fit

def analyze_gif_motion(gif_path):
    cap = cv2.VideoCapture(gif_path)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret: break
        frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    
    # 帧差 → 运动检测
    diffs = [cv2.absdiff(frames[i], frames[i+1]) for i in range(len(frames)-1)]
    
    # 追踪质心
    trajectories = {}
    for i, diff in enumerate(diffs):
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            M = cv2.moments(c)
            if M["m00"] > 50:  # 过滤噪声
                cx, cy = int(M["m10"]/M["m00"]), int(M["m01"]/M["m00"])
                # 匹配到已有元素或创建新的...
    
    # 速度分析 → 缓动判断
    for elem_id, points in trajectories.items():
        speeds = np.sqrt(np.sum(np.diff(points, axis=0)**2, axis=1))
        # 判断趋势
        if is_monotone_decreasing(speeds):
            easing = "ease-out"
        elif has_oscillation(speeds):
            easing = "spring"
        elif has_bounces(speeds):
            easing = "bounce"
        # ...
    
    return trajectories, easing_results
```

---

## 总结：解法关系图

```
                    ┌─────────────────┐
                    │ 我们的问题       │
                    │ GIF → 动画意图   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼───────┐ ┌───▼────┐ ┌──────▼──────┐
     │ A. 纯 VLM      │ │B. 纯CV │ │ D. 混合管线  │ ← 推荐
     │ (prompt 强化)   │ │(光流)  │ │ (CV+VLM)    │
     └────────┬───────┘ └───┬────┘ └──────┬──────┘
              │              │              │
              ▼              ▼              ▼
        定性描述         定量数据      定性+定量互补
        (能说类型)       (能给参数)    (类型准+参数准)
        
   短期用 A ──────────── 中期加 B ──────── 形成 D
```

### 行动优先级

1. **本周**：重构参考图提取 prompt（方案 A），用 Gemini 2.0 Flash 做视频分析，分步提取替代一次性描述
2. **下周**：加入 OpenCV 帧差分析 + 质心追踪（方案 B 的简化版），给 VLM 提供辅助数据
3. **之后按需**：如果效果仍不够，引入 CoTracker 做精细追踪，或对特定动画类型做分类模型

### 不建议做的

- 不要自己 fine-tune VLM — 训练数据太难构建，投入产出比极低
- 不要追求"一个模型搞定一切" — 这个问题本质上需要 CV（精确数据）+ VLM（语义理解）组合
- 不要花时间在"design-to-code"模型上 — 这个领域目前没有成熟的专用模型，都是通用 VLM + 领域 prompt
