# AI 创作一致性漂移问题：成熟解法调研

> 调研目标：系统梳理 AI 创作领域"一致性漂移"问题的已验证解法，找到可用于字符动画 HTML 场景的方案
> 调研日期：2026-05-26

---

## 问题定义

**一致性漂移**：AI 系统在生成系列作品时，即使使用相同的风格/角色描述，输出结果逐渐偏离预期，不像"同一个系列"。

一致性不只是"颜色统一"，至少包含三个层面：

| 层面 | 定义 | 漂移表现 |
|------|------|----------|
| 配色比例 | 主色/辅色/点缀色的占比关系 | 同一系列里有的作品蓝色占 70%，有的只占 30% |
| 造型语言 | 元素的形态风格（圆润/尖锐/几何/手绘等） | 有的帧用圆角，有的帧突然变方角 |
| 设计手法 | 布局方式、大小对比、留白比例等构成规则 | 有的密集有的空旷，没有统一的"呼吸感" |

---

## 子问题 1：图像生成中的角色/风格一致性

### 核心难题

**同一个 prompt 每次生成的结果不同，因为扩散模型的随机性本质上无法靠文字描述精确锁定视觉特征。**

文字描述是模糊的（"圆润的蓝色角色"有无数种视觉实现），而视觉一致性要求的是像素级/特征级的精确匹配。

### 成熟思路

| 思路名 | 解决什么 | 怎么用 | 在哪个生态里叫什么 | tradeoff |
|--------|----------|--------|-------------------|----------|
| **参考图注入（Reference Injection）** | 用一张参考图锁定风格/角色特征，让新生成的图继承其视觉基因 | 提供参考图 → 提取图像 embedding → 通过解耦交叉注意力注入到生成过程 | Midjourney `--cref`/`--sref`；IP-Adapter（全局/局部/人脸三种模式）；ControlNet Reference-Only | 越锁定越限制创意自由度；全局 embedding 保风格但丢细节，局部 embedding 保细节但太死板 |
| **自注意力共享（Shared Self-Attention）** | 让批量生成的多张图共享注意力层，使角色在不同场景中保持一致 | 同时输入 3-6 个 prompt → 在 UNet 的 self-attention 层中让图像互相"看到"彼此 | StoryDiffusion 的 Consistent Self-Attention；IP-Adapter 的 batch 模式 | 需要同时生成才有效（不能事后追加）；图越多越慢；5-6 张是实用上限 |
| **身份编码器（Identity Encoder）** | 用单张照片提取人脸/角色身份特征，在任意新生成中保持该身份 | 一张参考照片 → 人脸检测 + embedding 提取 → 注入扩散模型的条件通道 | InstantID（人脸 landmark + IP-Adapter 双通道）；PhotoMaker（Stacked ID Embedding）；IP-Adapter FaceID | 主要解决人脸，对全身/服装/姿态一致性较弱；非真人角色（卡通/抽象）效果差 |
| **微调冻结（LoRA Fine-tuning）** | 把特定角色/风格"烧进"模型权重，之后生成时自动带有该特征 | 准备 5-20 张参考图 → 用 LoRA 在 UNet 的 attention 层注入低秩矩阵 → 训练 500-15000 步 | Style LoRA；Character LoRA；DreamBooth + LoRA；Textual Inversion | 需要训练时间（几十分钟到几小时）；过拟合风险（太像参考图失去多样性）；每个角色/风格都需要单独训练 |
| **结构约束叠加（Structural Conditioning）** | 用骨骼/边缘/深度图等结构信息锁定姿态和构图，防止造型漂移 | 提供 pose/edge/depth/segmentation 条件图 → ControlNet 的零卷积机制将条件注入 UNet | ControlNet（Canny/Pose/Depth/Seg）；T2I-Adapter；多 ControlNet 叠加 | 只锁结构不锁风格，需要跟其他方案组合；需要预制条件图（增加工作量） |

### 思路之间的关系

```
                    ┌─ 锁定"谁"（角色身份）
                    │    ├─ 轻量级：参考图注入（IP-Adapter / --cref）
                    │    ├─ 批量级：自注意力共享（StoryDiffusion）
一致性需求 ─────────┤    └─ 永久级：LoRA 微调（Character LoRA）
                    │
                    ├─ 锁定"什么感觉"（风格）
                    │    ├─ 轻量级：参考图注入（IP-Adapter Style / --sref）
                    │    └─ 永久级：LoRA 微调（Style LoRA）
                    │
                    └─ 锁定"什么姿势/构图"（结构）
                         └─ ControlNet / 结构条件
```

**组合关系**：
- IP-Adapter（锁风格）+ ControlNet（锁结构）= 最常用组合
- LoRA（锁角色）+ ControlNet（锁姿态）= 动画序列常用
- StoryDiffusion（批量一致）+ IP-Adapter（参考注入）= 漫画/分镜制作

**互斥关系**：
- 多个 IP-Adapter 同时使用会互相干扰（权重需要仔细调配）
- LoRA 之间也会冲突（需要 LoRA merge 技术）

---

## 子问题 2：视频生成中的跨帧/跨镜头一致性

### 核心难题

**视频是时间序列，每一帧都是独立生成的，如何让前后帧在视觉上"连续"而不是"跳变"。**

比图像一致性更难的是：角色在不同镜头（不同角度、不同光照、不同动作）中还得是"同一个人"。

### 成熟思路

| 思路名 | 解决什么 | 怎么用 | 在哪个生态里叫什么 | tradeoff |
|--------|----------|--------|-------------------|----------|
| **时序注意力（Temporal Attention）** | 让相邻帧在生成时互相参照，保持帧间连续性 | 在 UNet 的 spatial attention 后加一层 temporal attention，让每帧 attend 到前后帧 | AnimateDiff；MagicAnimate 的 temporal_attention 模块；Wan2.1 的 3D 因果 VAE | 只解决相邻帧连续性，跨远距离镜头无效；长视频后期仍会漂移 |
| **外观编码器（Appearance Encoder）** | 从参考帧提取角色外观特征，注入到所有帧的生成过程 | 选一帧作为"角色锚点" → 编码外观特征 → 在每帧生成时作为额外条件注入 | MagicAnimate 的 appearance_encoder；LivePortrait 的 motion template 分离；EchoShot | 角色大幅度转身/遮挡时特征丢失；需要好的参考帧作为锚点 |
| **去闪烁后处理（Deflicker）** | 在已生成的视频上消除帧间风格/亮度跳变 | 生成完视频后，用光流估计帧间运动 → 在特征空间做帧间融合 → 输出平滑视频 | DiffSynth-Studio 的 FastBlend；Rerender-a-Video；CoDeF | 是"补救"不是"预防"——如果内容本身不一致，去闪烁也救不回来 |
| **关键帧插值（Keyframe Interpolation）** | 先生成关键帧确保一致，再在关键帧之间插入中间帧 | 人工/AI 生成关键帧（确保角色一致）→ 用视频插值模型填充中间帧 | StoryDiffusion 第二阶段；FILM 帧插值；Wan2.1 Image-to-Video | 关键帧之间差异太大时插值会失败；中间帧动作可能不自然 |
| **运动与外观解耦（Motion-Appearance Disentanglement）** | 把"角色长什么样"和"角色怎么动"分开控制 | 参考图提供外观 + 驱动视频/骨骼提供运动 → 模型只改动作不改外观 | LivePortrait（stitching + retargeting）；Animate Anyone；MagicPose | 解耦不彻底时运动会影响外观（比如表情变化导致脸型变化） |

### 思路之间的关系

**防线递进关系**：
1. **第一道防线**：外观编码器/IP-Adapter — 在生成时就注入一致性约束
2. **第二道防线**：时序注意力 — 让帧间互相参照，减少突变
3. **第三道防线**：去闪烁后处理 — 生成后补救微小的跳变

**应用场景分化**：
- 单人动画 → 运动与外观解耦（LivePortrait 类）
- 多镜头叙事 → 关键帧插值 + 外观编码器（StoryDiffusion 类）
- 长视频 → 时序注意力 + 去闪烁（AnimateDiff + FastBlend 类）

---

## 子问题 3：设计系统/Design Token 如何编码"比例关系"

### 核心难题

**传统 Design Token 只存"值"（蓝色是 #2563EB），不存"关系"（蓝色应该占画面 60%、出现在标题和按钮上）。而一致性漂移恰恰是"关系"层面的问题。**

### 成熟思路

| 思路名 | 解决什么 | 怎么用 | 在哪个生态里叫什么 | tradeoff |
|--------|----------|--------|-------------------|----------|
| **语义化 Token 分层（Semantic Token Layers）** | 让 token 不只是值，还表达"用途"和"关系" | 定义三层：原始值（blue-500）→ 语义用途（primary）→ 组件绑定（button-bg）。关系编码在中间层 | W3C Design Tokens 格式规范（$type + $value + aliases）；Style Dictionary 的 CTI 结构；shadcn/ui 的 background-foreground 配对 | 前期设计成本高；过度语义化会变得僵硬 |
| **比例约束系统（Proportional Scale System）** | 用数学关系而非固定值定义间距/字号/圆角，保证比例一致 | 定义一个基础单位 → 所有值都是基础单位的倍数 → 只允许使用预定义的倍数 | Tailwind CSS 的 `--spacing` 基础单位（4px 倍数）；shadcn/ui 的 `--radius` 派生比例（0.6x ~ 2.6x）；8pt grid system | 限制了精细调整的自由度；不适合所有设计风格 |
| **CSS 变量级联（CSS Variable Cascade）** | 改一个变量自动影响所有使用它的地方，防止"改了一处忘了其他" | 定义 CSS custom properties → 组件引用变量而非硬编码值 → 改变量 = 改全局 | Tailwind `@theme` 指令；CSS `:root` 变量系统；SCSS token maps | 只解决"值一致"，不解决"比例一致"；复杂组件可能需要很多变量 |
| **白名单约束（Allowlist Constraint）** | 只允许使用预定义的值，禁止随意新增，从根源防止漂移 | 设计系统只暴露有限的选项（5 种字号、8 种颜色、4 种圆角）→ 任何生成都必须从中选择 | Tailwind 的 utility-first 模式（只有定义了的才能用）；Figma 的 design library 限制；Penpot 的 Design Tokens | 过于严格会限制创意；需要前期投入大量精力定义完整的 token 集 |
| **组合 Token（Composite Token）** | 把多个相关属性打包成一个整体，确保它们总是一起出现 | 定义 `typography = { family + size + weight + lineHeight }`，使用时只能整体引用 | W3C 规范的 Composite Types（typography/border/shadow/gradient）；Figma 的 text styles/effect styles | 灵活性降低；组合越大越难适配特殊场景 |

### 思路之间的关系

**从"值"到"规则"的递进**：
```
Level 0: 硬编码值（color: #2563EB） — 最容易漂移
Level 1: CSS 变量（color: var(--primary)） — 值一致
Level 2: 语义 Token（bg-primary vs text-primary） — 用途一致
Level 3: 比例系统（spacing = base × n） — 节奏一致
Level 4: 白名单约束（只能用这 5 个字号） — 强制一致
Level 5: 组合 Token（typography 样式包） — 组合一致
```

**对 AI 生成的特殊意义**：
- AI 不像人类设计师会"凭感觉"保持一致，它每次都是独立决策
- 所以 Level 4（白名单）和 Level 5（组合 Token）对 AI 场景特别重要
- 给 AI 的不应该是"蓝色"，而应该是"从这 5 个颜色里选，主色占 60%，辅色占 30%，点缀占 10%"

---

## 子问题 4：代码生成中的视觉一致性

### 核心难题

**LLM 生成 HTML/CSS 时，每次对话都是"无状态"的——它不记得上次用了什么颜色、什么字号、什么间距比例。**

### 成熟思路

| 思路名 | 解决什么 | 怎么用 | 在哪个生态里叫什么 | tradeoff |
|--------|----------|--------|-------------------|----------|
| **CSS Token 文件注入（Token File Injection）** | 让 LLM 生成代码时必须引用预定义的变量，而非自由发挥 | 在 prompt 中提供 CSS 变量文件 → 要求 AI 只使用这些变量 → 代码审查验证是否遵守 | v0.dev + shadcn/ui theming；Claude Artifacts + Tailwind config；Cursor rules + design tokens | 需要维护 token 文件；AI 有时会"忘记"使用变量而直接写死值 |
| **组件库约束（Component Library Constraint）** | 不让 AI 从零写样式，只允许组合预制组件 | 提供组件库（按钮/卡片/标题等）→ AI 只能调用这些组件 → 风格天然一致 | shadcn/ui 作为 v0 的组件源；Tailwind UI；Radix + 自定义主题 | 创意自由度大幅降低；不适合高度定制的视觉设计 |
| **风格 Prompt 模板（Style Prompt Template）** | 在每次生成时注入统一的风格描述，减少随机漂移 | 写一份"风格规范 prompt"（字体、配色、间距规则）→ 每次调用 AI 时都附加 | Claude CLAUDE.md 中的风格规则；ChatGPT Custom Instructions；Cursor .cursorrules | 依赖 LLM 的"遵守度"，不是硬约束；prompt 越长越容易被忽略 |
| **后置验证+修复（Post-generation Validation）** | 生成后检查是否符合风格规范，不符合则自动修复 | AI 生成代码 → 自动化脚本检查（是否使用了定义外的颜色？间距是否是 4px 倍数？）→ 不通过则反馈给 AI 修复 | ESLint/Stylelint 自定义规则；Code2Video 的 VLM 反馈循环；Crayotter 的奖励函数 | 增加生成时间（多一轮往返）；验证规则需要提前定义完善 |
| **模板继承（Template Inheritance）** | 所有生成的页面共享同一个 base template，只替换内容区域 | 定义 base.html（含全局样式、布局骨架）→ AI 只生成内容区块 → 拼装到模板中 | Jinja2/Handlebars 模板系统；Web Components + slots；iframe 嵌入 | 布局自由度降低；模板本身的维护成本 |

### 思路之间的关系

**约束强度递进**：
```
弱约束 ← ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ → 强约束

风格 Prompt    CSS Token 注入    后置验证    组件库约束    模板继承
（靠 AI 自觉）  （提供变量）    （生成后检查）  （限定选项）  （锁定框架）
```

**推荐组合**：
- **日常生成**：CSS Token 注入 + 风格 Prompt = 性价比最高
- **系列作品**：模板继承 + CSS Token 注入 + 后置验证 = 最可靠
- **快速原型**：组件库约束 = 最快最一致（但最不灵活）

---

## 对应到字符动画 HTML 场景怎么用

### 场景特点

我们的场景是：用 AI 生成多个 HTML 动画文件，它们需要看起来是"同一个系列"。每个动画是独立的 `.html` 文件，用 CSS/JS 实现字符动画。

### 一致性漂移在我们场景的具体表现

| 漂移类型 | 具体例子 |
|----------|----------|
| 配色漂移 | 第一个动画用深蓝+金色，第三个动画不知不觉变成浅蓝+橙色 |
| 造型漂移 | 前几个动画角色是圆润风格，后面突然变尖锐 |
| 排版漂移 | 有的动画文字大而稀疏，有的密而小 |
| 动效漂移 | 有的用缓动 ease-out，有的用 linear，节奏不统一 |
| 比例漂移 | 有的角色占画面 80%，有的只占 40% |

### 推荐方案：三层防护

#### 第一层：Token 文件（硬约束）

创建一个 `style-tokens.css` 文件，所有动画必须引用：

```css
/* style-tokens.css — 系列级配置 */
:root {
  /* 配色 — 不只是色值，还有比例规则 */
  --color-primary: oklch(0.55 0.15 250);     /* 主色：占画面 60% */
  --color-secondary: oklch(0.75 0.10 80);    /* 辅色：占画面 25% */
  --color-accent: oklch(0.85 0.20 30);       /* 点缀：占画面 10% */
  --color-bg: oklch(0.15 0.02 250);          /* 背景：占画面 5% */
  
  /* 造型语言 */
  --border-radius: 12px;                     /* 圆润风格 */
  --shape-style: rounded;                    /* rounded | angular | organic */
  
  /* 比例系统 */
  --unit: 8px;                               /* 基础单位 */
  --character-scale: 0.6;                    /* 角色占画面的比例 */
  --text-scale-ratio: 1.25;                  /* 字号递增比例 */
  
  /* 动效节奏 */
  --ease-default: cubic-bezier(0.4, 0, 0.2, 1);
  --duration-fast: 200ms;
  --duration-normal: 400ms;
  --duration-slow: 800ms;
}
```

#### 第二层：风格 Spec 文档（软约束）

在 prompt 中附加的风格规范，描述"为什么"和"怎么判断"：

```markdown
## 系列风格规范

### 配色规则
- 主色（深蓝）用于：角色主体、重要文字
- 辅色（金色）用于：装饰元素、次要信息
- 点缀色（亮橙）用于：强调动作、转场高光
- 禁止：使用定义外的颜色；主色和辅色面积反转

### 造型规则
- 所有形状使用 12px 圆角，不出现直角
- 角色由简单几何形状组成（圆+圆角矩形），不出现复杂曲线
- 字符用等宽字体渲染，字间距统一

### 动效规则
- 所有运动使用 ease-out（减速停止），禁用 linear
- 入场动画 400ms，退场 200ms，循环动画 800ms
- 角色移动速度统一：每秒移动画面宽度的 20%
```

#### 第三层：后置验证（自动检查）

生成动画后，用脚本检查是否违反规则：

```
检查项：
□ 是否引用了 style-tokens.css（或内联了所有 token 变量）
□ 是否使用了 token 定义外的颜色值
□ border-radius 是否统一为 --border-radius
□ 动画 duration 是否使用了预定义的三个值
□ ease 函数是否是 --ease-default
□ 角色尺寸是否约等于画面的 --character-scale
```

### 各领域解法的借鉴映射

| 领域解法 | 在我们场景对应什么 |
|----------|-------------------|
| IP-Adapter 参考图注入 | → 在 prompt 中附加"参考动画截图"描述，让 AI 对齐视觉 |
| LoRA 微调 | → 不适用（我们不训练模型），但思想可借鉴：积累"好的生成结果"作为 few-shot 示例 |
| StoryDiffusion 自注意力共享 | → 批量生成时把系列所有动画的 spec 放在同一个 context 中，让它们互相参照 |
| Design Token 白名单 | → **直接可用**：style-tokens.css 就是白名单 |
| Tailwind @theme 约束 | → **直接可用**：可以用 Tailwind 作为动画的样式框架，天然有约束 |
| shadcn/ui 组合 Token | → 可以定义"动画组合 Token"：一个 token 包含颜色+时长+缓动的完整组合 |
| 后置验证（Code2Video 思路） | → **直接可用**：生成后跑验证脚本，不通过就反馈给 AI 修复 |
| Crayotter 经验记忆 | → 积累"哪些 prompt 产出了好结果"，下次生成时注入作为参考 |
| 模板继承 | → **直接可用**：定义 base-animation.html 模板，AI 只填充动画内容区 |

### 实施优先级

1. **立即做**：创建 style-tokens.css + 风格 Spec 文档（第一层+第二层）
2. **第二步**：定义 base-animation.html 模板，让所有动画继承
3. **第三步**：写验证脚本（第三层），集成到生成流程
4. **持续做**：积累好结果作为 few-shot 参考（经验记忆思路）

---

## 总结：一致性问题的本质

一致性漂移的本质是**约束信息在传递过程中的衰减**：

- 图像生成：prompt 的语义 → 像素的转化过程中丢失精度
- 视频生成：帧间的约束随时间距离增大而减弱
- 代码生成：每次对话都是独立的，没有"记忆"

**所有成熟解法的共同逻辑**：把模糊的语义约束转化为精确的结构化约束。

```
人脑中的"感觉"
    ↓ 转化为
结构化的约束（token / embedding / condition / template）
    ↓ 注入到
生成过程的每一步
    ↓ 验证
输出是否符合约束
```

对我们的字符动画场景：
- **不要指望 prompt 描述能保持一致性** — 语言太模糊
- **用代码级约束（CSS Token + Template）替代语言级约束** — 代码是精确的
- **生成后验证** — 兜底防护
- **积累好案例** — 让 AI 有"视觉参照物"而非只有文字描述
