# 粒子系统物理参数预设调研

> 调研目标：找到成熟的"动画类型→物理参数"映射表，供 HTML Canvas 字符动画系统直接参考。

---

## 核心发现

粒子物理参数的本质是 **4 个力的平衡**：初速（发射冲量）、重力（持续向下拉力）、阻力（速度衰减）、随机扰动（横向漂移/湍流）。不同动画效果就是这 4 个旋钮的不同组合。

---

## 参考来源

| # | 来源 | 类型 | 价值 |
|---|------|------|------|
| 1 | **PixiJS Particle Emitter** (pixijs-userland/particle-emitter) | Web 粒子库 | 最直接可用，有 rain/snow/sparks/explosion/flame/fountain/smoke/bubbles 等完整预设，参数为像素单位 |
| 2 | **tsParticles** (tsparticles/tsparticles) | Web 粒子库 | 20+ 预设（fire/snow/confetti/fireworks/fountain/firefly/hyperspace），有重力、衰减、摆动等参数 |
| 3 | **EaselJS Sparkles** (CreateJS) | Canvas 粒子示例 | 简洁的火花物理：gravity=0.1/frame, bounce=0.8-0.9, velocity 0-15 |
| 4 | **sketch.js particles** (soulwire) | Canvas 粒子库 | drag=0.9-0.99, radius decay=0.96/frame, wander=0.5-2.0 |
| 5 | **Unity ParticleSystem** | 游戏引擎 | 工业标准参数模型（lifetime, startSpeed, gravityModifier, damping），文档无默认值但模型最完整 |

---

## 通用预设表

以下参数基于 PixiJS Particle Emitter + tsParticles + EaselJS 的实际预设提取，统一换算为 **Canvas 像素坐标系**（y 轴向下为正，速度单位=px/s，重力单位=px/s²）。

### 参数说明

| 参数 | 含义 | 单位 |
|------|------|------|
| lifetime | 粒子从出生到消亡的时间 | 秒 |
| speed | 初始发射速度 | px/s |
| gravity | 向下加速度（正值=向下） | px/s² |
| drag | 速度衰减系数（每帧乘以此值，1=无衰减） | 0-1 |
| spread | 发射方向的散开角度（以主方向为中心） | 度 |
| emitRate | 每秒发射粒子数 | 个/s |
| sizeStart→End | 粒子大小变化（相对值，1=初始大小） | 倍数 |
| alphaStart→End | 透明度变化 | 0-1 |

---

### 1. 仙女棒火花 (Sparkler)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 0.25 - 0.5s | PixiJS sparks: 0.25-0.5s |
| speed | 150 - 500 px/s | PixiJS sparks: start 1000 → end 200（我们画布小，等比缩放） |
| gravity | 200 - 400 px/s² | 中等重力，火花要有弧线但不立刻坠落 |
| drag | 0.95 - 0.97 | 速度衰减快，火花短命 |
| spread | 200° (接近全向) | PixiJS sparks: 225°-320° rotation range = ~95° 半角 |
| emitRate | 60 - 100 个/s | 项目已有预设: 66/s (每15ms一个) |
| sizeStart→End | 1.0 → 0.3 | 越来越小 |
| alphaStart→End | 1.0 → 0.0 | 完全淡出 |

**特征**：高初速 + 中重力 + 高阻力 + 大散角 = 短促放射状轨迹

---

### 2. 雪花飘落 (Snow)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 4 - 8s | PixiJS snow: 4s; tsParticles snow: 长生命 |
| speed | 50 - 200 px/s | PixiJS snow: 200 (垂直向下) |
| gravity | 20 - 50 px/s² | 极弱重力，近乎匀速下落 |
| drag | 0.99 - 0.995 | 几乎无衰减（空气托住） |
| spread | 20° (近乎垂直) | PixiJS snow: 50°-70° start angle（偏垂直） |
| emitRate | 30 - 80 个/s | PixiJS: frequency 0.004 × 1000 maxParticles ≈ 250/s（大画布），小画布等比缩小 |
| sizeStart→End | 0.5 → 1.0 (微微变大) | PixiJS snow: 0.15→0.2 |
| alphaStart→End | 0.7 → 0.4 | 微微淡出但不消失 |
| **横向漂移** | wobble ±5-20 px, 周期 2-4s | tsParticles snow: wobble distance=20, speed ±5 |

**特征**：低速 + 弱重力 + 极低阻力 + 正弦横摆 = 轻盈飘荡

---

### 3. 爆炸 (Explosion)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 0.3 - 0.5s | PixiJS explosion: 0.5s |
| speed | 200 - 600 px/s | PixiJS explosion: 200 (较小爆炸); EaselJS: burst 100-200个 |
| gravity | 0 - 100 px/s² | 爆炸初期重力忽略不计 |
| drag | 0.90 - 0.94 | 高阻力快速减速 |
| spread | 360° (全向) | PixiJS explosion: rotation 0-360° |
| emitRate | 瞬发 50-200 个 | PixiJS: emitterLifetime=0.31s, burst模式 |
| sizeStart→End | 1.0 → 0.3 | PixiJS: scale 1→0.3 |
| alphaStart→End | 0.8 → 0.1 | PixiJS: alpha 0.8→0.1 |

**特征**：瞬发高速 + 无/弱重力 + 高阻力 + 全向 = 球形扩散后迅速消散

---

### 4. 火焰 (Flame/Fire)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 0.1 - 0.75s | PixiJS flame: 0.1-0.75s |
| speed | 300 - 500 px/s | PixiJS flame: 500 (向上) |
| gravity | -100 ~ -200 px/s² (负值=向上浮力) | 火焰向上，用负重力或初始向上速度 |
| drag | 0.96 - 0.98 | 中等衰减 |
| spread | 10° - 20° (窄锥形) | PixiJS flame: 265°-275° (向上±5°) |
| emitRate | 100 - 300 个/s | PixiJS: frequency 0.001 × maxParticles = 持续高频 |
| sizeStart→End | 0.25 → 0.75 | PixiJS flame: 0.25→0.75 (火焰扩散变大) |
| alphaStart→End | 0.62 → 0.0 | PixiJS flame: 0.62→0 |

**特征**：高频窄锥向上 + 浮力 + 中阻力 + 尺寸先增后淡 = 舔舐上升

---

### 5. 烟雾 (Smoke)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 0.4 - 2.0s | PixiJS cartoonSmoke: 0.4-0.7s; gas: 1.8-2.0s |
| speed | 50 - 700 px/s (差距大看效果) | cartoonSmoke: start 700→end 50; gas: 10 |
| gravity | -30 ~ -80 px/s² (微上浮) | 烟雾缓慢上升 |
| drag | 0.92 - 0.96 | 烟减速明显 |
| spread | 360° (随机方向) | PixiJS: rotation 0-360° |
| emitRate | 20 - 100 个/s | 视浓度而定 |
| sizeStart→End | 0.1 → 1.2 (大幅扩散) | PixiJS cartoonSmoke: 0.1→1.2 |
| alphaStart→End | 0.74 → 0.0 | PixiJS: 0.74→0 |

**特征**：起始快速减速 + 微上浮 + 大幅尺寸膨胀 + 淡出 = 蓬松扩散

---

### 6. 雨 (Rain)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 0.5 - 1.0s | PixiJS rain: 0.81s |
| speed | 1500 - 3000 px/s | PixiJS rain: 3000 (极快的竖线) |
| gravity | 0 (匀速) | 雨滴已达终端速度 |
| drag | 1.0 (无衰减) | 匀速下落 |
| spread | 0° - 5° (几乎垂直) | PixiJS rain: rotation 65° (偏斜，模拟有风) |
| emitRate | 200 - 500 个/s | PixiJS: frequency 0.004 × 1000 max |
| sizeStart→End | 1.0 → 1.0 (不变) | 雨滴大小恒定 |
| alphaStart→End | 0.5 → 0.5 (恒定半透明) | PixiJS rain: alpha 0.5 static |

**特征**：极高速匀速 + 零重力零阻力 + 近垂直 + 恒定外观 = 密集线条

---

### 7. 喷泉 (Fountain)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 0.25 - 0.5s (上升段) + 更长（含下落） | PixiJS fountain: 0.25-0.5s |
| speed | 400 - 600 px/s (向上) | PixiJS fountain: 600 |
| gravity | 1500 - 2000 px/s² | PixiJS fountain: acceleration y=2000 |
| drag | 0.99 (几乎无阻力) | 喷泉在空气中阻力小 |
| spread | 20° - 40° (窄锥向上) | PixiJS: 260°-280° (向上±10°) |
| emitRate | 100 - 300 个/s | PixiJS: frequency 0.001, 持续 |
| sizeStart→End | 0.5 → 1.0 | PixiJS: 0.5→1.0 |
| alphaStart→End | 1.0 → 0.3 | PixiJS: 1.0→0.31 |

**特征**：高初速向上 + 强重力 = 抛物线轨迹，到顶减速后回落

---

### 8. 气泡上浮 (Bubbles)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 0.5 - 3.0s | PixiJS bubbleSpray: 0.5-1.0s; tsParticles bubbles: 3s |
| speed | 200 - 600 px/s (向上) | PixiJS: start 600→end 200 |
| gravity | -50 ~ -150 px/s² (浮力) | 持续向上 |
| drag | 0.97 - 0.99 | 液体阻力 |
| spread | 20° - 40° | PixiJS: 260°-280° |
| emitRate | 10 - 50 个/s | PixiJS: frequency 0.008, emitterLife 0.15s |
| sizeStart→End | 0.01 → 0.8 (从小变大) | PixiJS: 0.01→0.8 |
| alphaStart→End | 1.0 → 0.1 | PixiJS: 1.0→0.12 |

**特征**：向上 + 浮力 + 液体阻力 + 尺寸膨胀 = 气泡感

---

### 9. 烟花 (Fireworks)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| **上升阶段（火箭）** | | |
| lifetime | 1 - 2s | tsParticles fireworks: 1-2s |
| speed | 300 - 600 px/s (向上) | tsParticles: 10-20 (归一化单位) |
| gravity | -500 ~ -800 px/s² (反向=向上推) | tsParticles: gravity 15, inverse=true |
| drag | 0.98 | 上升段轻微减速 |
| **爆炸阶段** | | |
| lifetime | 1 - 2s | tsParticles: 1-2s |
| speed | 150 - 450 px/s (全向) | tsParticles: 5-15 |
| gravity | 150 - 300 px/s² | tsParticles: gravity 5 (归一化) |
| drag/decay | 0.90 - 0.93 | tsParticles: decay 0.075-0.1 |
| spread | 360° | 全向爆开 |
| emitRate | 瞬发 75-150 个 | tsParticles: split rate 75-150 |
| alphaStart→End | 1.0 → 0.1 | 动画速度 0.7 |
| trail | 5-10 帧尾迹 | tsParticles: trail 5-10 |

**特征**：两段式（上升+爆开），爆开后重力+高衰减 = 垂花效果

---

### 10. 五彩纸屑 (Confetti)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 3 - 4s | tsParticles confetti: ~3.3s |
| speed | 300 - 500 px/s (向上发射) | tsParticles: speed 45 (归一化) |
| gravity | 600 - 980 px/s² | tsParticles: gravity 9.81 (归一化≈真实重力) |
| drag/decay | 0.90 | tsParticles: decay 0.1 |
| spread | 45° (向上为主) | tsParticles: angle 45° |
| emitRate | 瞬发 50 个 | tsParticles: initial count 50 |
| sizeStart→End | 1.0 → 1.0 (不变) | 纸屑大小恒定 |
| alphaStart→End | 1.0 → 0.0 | 动画速度 0.5 |
| **旋转** | 0-360°, 转速 60°/s | tsParticles: rotate speed 60 |
| **摇摆** | 距离 30px, 速度 ±15 | tsParticles: wobble distance 30, speed -15~15 |
| **翻滚** | 速度 15-25, 暗化 25% | tsParticles: roll speed 15-25, darken 25 |

**特征**：向上发射 + 真实重力 + 旋转/摇摆/翻滚 = 纸片飘舞

---

### 11. 萤火虫 (Firefly)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 5s | tsParticles firefly: duration 5s |
| speed | 30 - 100 px/s | tsParticles: speed 3 (归一化) |
| gravity | 0 | 无重力，自由漂浮 |
| drag | 0.99 | 极低阻力 |
| spread | 360° (随机方向) | 全向慢速漫游 |
| emitRate | 5 - 15 个/s | 稀疏分布 |
| sizeStart→End | 1.0 → 1.0 | 大小恒定 3-6px |
| alphaStart→End | 呼吸闪烁 0.1↔1.0 | tsParticles: opacity 0.1-1.0, animation speed 3 |

**特征**：极慢 + 无重力 + 透明度呼吸循环 = 幽幽明灭

---

### 12. 星空闪烁 (Stars/Twinkle)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | ∞ (持续存在) | tsParticles stars: 无销毁 |
| speed | 0.1 - 1 px/s (近静止) | tsParticles: speed 0.1 |
| gravity | 0 | 无重力 |
| drag | 1.0 | 无衰减 |
| spread | 360° | 随机微动 |
| emitRate | N/A (一次性放置) | tsParticles: number 100 |
| sizeStart→End | 1-3px 恒定 | tsParticles: 1-3 |
| alphaStart→End | 0↔1 循环闪烁 | 动画速度 1 |

**特征**：几乎静止 + 透明度循环 = 闪烁效果

---

### 13. 超空间/星轨 (Hyperspace/Warp)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 5s | tsParticles hyperspace: 5s |
| speed | 300 - 600 px/s (向外) | tsParticles: speed 10, 归一化 |
| gravity | 0 | 无重力 |
| drag/decay | 0.995 (极低衰减) | tsParticles: decay 0.005 |
| spread | 360° (从中心向外) | direction: outside |
| emitRate | 100 个/s | tsParticles: rate 10, delay 0.1s |
| sizeStart→End | 3px 恒定 | 线条恒定 |
| alphaStart→End | 1.0 (恒定) | 不淡出，靠离开画布销毁 |
| **尾迹** | 15帧长 | tsParticles: trail length 15 |

**特征**：从中心高速向外 + 直线 + 长尾迹 = 星际跃迁线条

---

### 14. 落叶 (Falling Leaves)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 5 - 10s | 类比雪花，但更慢 |
| speed | 30 - 80 px/s | 比雪花慢 |
| gravity | 15 - 30 px/s² | 极弱重力 |
| drag | 0.99 | 空气阻力大 |
| spread | 30° (偏垂直) | 主向下，微偏 |
| emitRate | 5 - 15 个/s | 稀疏 |
| sizeStart→End | 1.0 → 0.8 | 微缩 |
| alphaStart→End | 1.0 → 0.6 | 微淡 |
| **旋转** | 速度 30-90°/s | 叶子翻转 |
| **横向摇摆** | 幅度 30-60px, 周期 2-5s | 正弦横漂 |

**特征**：极慢下落 + 大幅摇摆 + 旋转 = 飘叶感

---

### 15. 发光尘埃/粒子上浮 (Rising Dust/Motes)

| 参数 | 值 | 来源/依据 |
|------|-----|-----------|
| lifetime | 3 - 6s | 类比气泡但更轻 |
| speed | 20 - 60 px/s (向上) | 极慢 |
| gravity | -10 ~ -30 px/s² (微浮力) | 持续缓慢上升 |
| drag | 0.995 | 几乎无阻力 |
| spread | 40° - 60° (偏上) | 大致向上但有散开 |
| emitRate | 10 - 30 个/s | 中等密度 |
| sizeStart→End | 1.0 → 0.5 | 缩小 |
| alphaStart→End | 0.6 → 0.0 | 缓慢淡出 |

**特征**：极低速上浮 + 微浮力 + 缓慢淡出 = 梦幻光尘

---

## 在 HTML Canvas 场景中的适配说明

### 1. 单位换算

上述参数来自不同引擎，统一到 Canvas 时需注意：

| 原始环境 | 典型画布 | 我们的画布 | 换算建议 |
|----------|----------|-----------|----------|
| PixiJS 示例 | 960×600 | 我们用 innerWidth×innerHeight | 速度按比例缩放，或直接用像素值（多数已是像素） |
| tsParticles | 归一化单位 | px | 速度×30-50 可得到合理px值；gravity 9.81→约 300-500 px/s² |
| Unity | 世界单位 | px | 无法直接换算，参考比例关系即可 |

### 2. 帧率处理

**关键**：所有速度/加速度必须乘以 `deltaTime`（秒），不能依赖固定帧率。

```javascript
// 正确做法
particle.vy += gravity * dt;
particle.vx *= Math.pow(drag, dt * 60); // 将 per-frame drag 转为时间相关
particle.x += particle.vx * dt;
particle.y += particle.vy * dt;
```

### 3. 性能约束

HTML Canvas 渲染文字比渲染圆形慢 5-10 倍。参数适配建议：

| 约束 | 调整策略 |
|------|----------|
| 字符粒子渲染慢 | emitRate 降为上述值的 1/3 ~ 1/5 |
| 手机端性能差 | 最大粒子数限制 100-200 |
| 字符有大小 | sizeStart 最小 8px（否则看不清字） |
| 字符不能太密 | 适当加大散角或降频 |

### 4. drag 的实现方式

两种常见实现，效果不同：

```javascript
// 方式 A：指数衰减（推荐，帧率无关）
v *= Math.pow(drag, dt * 60);

// 方式 B：线性阻力（更物理但需要调参）
v -= v * dragCoefficient * dt;
```

我们项目推荐**方式 A**，因为参数直觉更好（drag=0.95 意味着每帧保留95%速度）。

### 5. 摇摆/漂移的实现

雪花、纸屑、落叶等需要横向摆动：

```javascript
// 正弦横摆
particle.x += Math.sin(particle.age * wobbleFreq + particle.phase) * wobbleAmp * dt;
```

其中 `wobbleFreq = 2π / 周期(s)`，`wobbleAmp = 最大偏移(px)`，`phase = 随机初相位`。

---

## 速查对照表（简化版）

| 动画类型 | 寿命 | 初速 | 重力 | 阻力 | 散角 | 核心特征 |
|----------|------|------|------|------|------|----------|
| 仙女棒 | 0.3-0.5s | 高(150-500) | 中(200-400) | 高(0.95) | 200° | 短促放射 |
| 雪花 | 4-8s | 低(50-200) | 弱(20-50) | 极低(0.99) | 20° | 匀速+横摆 |
| 爆炸 | 0.3-0.5s | 高(200-600) | 无~弱(0-100) | 高(0.90) | 360° | 瞬发球扩 |
| 火焰 | 0.1-0.75s | 高(300-500) | 负(-100~-200) | 中(0.97) | 10-20° | 窄锥上升 |
| 烟雾 | 0.4-2s | 高→低(50-700) | 负(-30~-80) | 高(0.93) | 360° | 膨胀淡出 |
| 雨 | 0.5-1s | 极高(1500-3000) | 0 | 0(1.0) | 0-5° | 匀速竖线 |
| 喷泉 | 0.5-1.5s | 高(400-600) | 强(1500-2000) | 无(0.99) | 20-40° | 抛物线 |
| 气泡 | 0.5-3s | 中(200-600) | 负(-50~-150) | 中(0.98) | 20-40° | 上浮膨胀 |
| 烟花 | 1-2s+1-2s | 高→中 | 反→正 | 低→高 | 窄→360° | 两段式 |
| 纸屑 | 3-4s | 中(300-500) | 强(600-980) | 高(0.90) | 45° | 摇摆翻滚 |
| 萤火虫 | 5s+ | 极低(30-100) | 0 | 无(0.99) | 360° | 呼吸明灭 |
| 星空 | ∞ | 0 | 0 | - | - | 闪烁 |
| 超空间 | 5s | 高(300-600) | 0 | 极低(0.995) | 360°外扩 | 长尾迹 |
| 落叶 | 5-10s | 极低(30-80) | 极弱(15-30) | 低(0.99) | 30° | 旋转横摆 |
| 光尘上浮 | 3-6s | 极低(20-60) | 负(-10~-30) | 无(0.995) | 40-60° | 缓慢淡出 |

---

## Tradeoff 与选择建议

### 物理精确 vs 视觉正确

- **物理精确**：用真实重力 980px/s²、真实空气阻力系数 → 看起来"对"但可能不好看
- **视觉正确**（推荐）：参数为视觉效果服务，不追求物理真实 → 火焰可以用负重力，纸屑可以比真实慢

### 参数复杂度 vs 效果丰富度

| 层级 | 参数数量 | 适用场景 |
|------|----------|----------|
| 基础 | 4个（lifetime, speed, gravity, alpha） | 火花、雨等简单效果 |
| 标准 | 7个（+drag, spread, size曲线） | 大多数效果 |
| 高级 | 10+个（+wobble, rotation, trail） | 纸屑、落叶等复杂效果 |

**建议**：我们的字符动画系统从"标准"层开始，按需加 wobble/rotation。

---

## 下一步行动

1. 将此表转化为代码中的 preset 对象（如 `PHYSICS_PRESETS.sparkler`）
2. 每个 preset 做 ±30% 的随机化（避免所有粒子行为一致）
3. 提供一个调参 UI（或 URL 参数）方便实时微调
4. 先实现 3 个核心效果验证参数：仙女棒（已有）、雪花（新）、爆炸（新）
