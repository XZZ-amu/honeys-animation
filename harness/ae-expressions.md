# AE 表达式 → Canvas 代码对照表

常用的动效表达式，经过 AE 社区验证，可直接用在我们的 HTML Canvas 动画中。

---

## 1. 弹跳（Bounce）

物体落地后反弹，每次反弹高度衰减。

**AE 表达式：**
```javascript
e = 0.7;        // 弹性系数（0-1，越高弹越多次）
g = 3000;       // 重力
nMax = 5;       // 最大弹跳次数
t = time - inPoint;
v0 = velocity[1]; // 初始速度

// 计算当前在第几次弹跳
tCur = t;
for (n = 0; n < nMax; n++) {
  tBounce = 2 * v0 / g * Math.pow(e, n);
  if (tCur < tBounce) break;
  tCur -= tBounce;
  v0 *= e;
}
y = -v0 * tCur + g * tCur * tCur / 2;
value + [0, y]
```

**Canvas 等价：**
```javascript
function bounceY(t, initialVelocity, gravity, elasticity, maxBounces) {
  let v0 = initialVelocity;
  let tCur = t;
  for (let n = 0; n < maxBounces; n++) {
    const tBounce = 2 * v0 / gravity;
    if (tCur < tBounce) break;
    tCur -= tBounce;
    v0 *= elasticity;
  }
  return -(v0 * tCur - 0.5 * gravity * tCur * tCur);
}
```

**推荐参数：**
- 轻物（字母、纸片）：elasticity=0.5-0.6, gravity=1500-2500
- 中物（球、按钮）：elasticity=0.65-0.75, gravity=3000-4000
- 重物（石头、金属）：elasticity=0.3-0.4, gravity=5000+

---

## 2. 弹性过冲（Overshoot / Elastic）

物体到达目标位置时超过一点再弹回来，像弹簧。

**AE 表达式：**
```javascript
amp = 0.06;     // 过冲幅度
freq = 3.0;     // 振荡频率
decay = 6.0;    // 衰减速度
t = time - inPoint;
x = amp * Math.sin(freq * t * 2 * Math.PI) / Math.exp(decay * t);
value + value * x
```

**Canvas 等价：**
```javascript
function overshoot(t, amp, freq, decay) {
  if (t < 0) return 0;
  return amp * Math.sin(freq * t * Math.PI * 2) * Math.exp(-decay * t);
}
// 使用：scale = 1 + overshoot(elapsed, 0.3, 3, 6)
```

**推荐参数：**
- 轻快弹入：amp=0.2-0.3, freq=3-4, decay=5-7
- 柔和弹入：amp=0.1-0.15, freq=2, decay=8-10
- 夸张弹入：amp=0.4-0.5, freq=2.5, decay=4

---

## 3. 惯性滑动（Inertia / Slide）

物体被推一下后靠惯性滑动，逐渐减速停下。

**AE 表达式：**
```javascript
// 在关键帧停止后继续滑动
t = time - thisLayer.marker.key(1).time;
v = velocityAtTime(thisLayer.marker.key(1).time);
decay = 4;
value + v * (1 - Math.exp(-decay * t)) / decay
```

**Canvas 等价：**
```javascript
function inertiaSlide(t, initialVelocity, friction) {
  // 指数衰减：物体以初速开始，摩擦力逐渐停下
  return initialVelocity * (1 - Math.exp(-friction * t)) / friction;
}
// displacement = inertiaSlide(elapsed, 500, 4)
```

**推荐参数：**
- 冰面滑动：friction=1-2（滑很远）
- 普通桌面：friction=4-6（中等距离）
- 粗糙表面：friction=8-12（很快停下）

---

## 4. 摆动衰减（Wiggle Decay）

随机抖动逐渐平息。适合"震动后恢复平静"。

**AE 表达式：**
```javascript
freq = 10;      // 抖动频率
amp = 30;       // 初始幅度
decay = 3;      // 衰减速度
t = time - inPoint;
wiggle(freq, amp * Math.exp(-decay * t))
```

**Canvas 等价（确定性版本）：**
```javascript
function wiggleDecay(t, freq, amp, decay, seed) {
  const envelope = amp * Math.exp(-decay * t);
  // 用多个 sin 叠加模拟随机感
  const noise = Math.sin(t * freq * 6.28 + seed) * 0.6
              + Math.sin(t * freq * 4.17 + seed * 2.3) * 0.3
              + Math.sin(t * freq * 9.81 + seed * 0.7) * 0.1;
  return envelope * noise;
}
// offsetX = wiggleDecay(elapsed, 10, 30, 3, 42)
```

**推荐参数：**
- 轻微颤抖（风铃）：freq=5-8, amp=3-8, decay=2-3
- 中等震动（受击）：freq=12-18, amp=15-30, decay=4-6
- 剧烈抖动（爆炸后）：freq=20-30, amp=30-60, decay=3-4

---

## 5. 循环摆动（Loop Oscillation）

持续的周期性运动，不衰减。适合呼吸感、悬浮、轻微晃动。

**AE 表达式：**
```javascript
amp = 20;
freq = 0.5;    // Hz
value + [0, amp * Math.sin(time * freq * 2 * Math.PI)]
```

**Canvas 等价：**
```javascript
function oscillate(t, amp, freq, phase) {
  return amp * Math.sin(t * freq * Math.PI * 2 + (phase || 0));
}
// y = baseY + oscillate(elapsed, 10, 0.5)
```

**推荐参数：**
- 呼吸/悬浮：amp=5-15px, freq=0.3-0.6Hz
- 轻微晃动：amp=2-5px, freq=0.8-1.5Hz
- 脉搏/跳动：amp=3-8px, freq=1.5-3Hz

---

## 6. 延迟/跟随（Delay / Follow Through）

多个元素做相同运动但有时间差，产生"波浪"或"拖尾"效果。

**AE 表达式：**
```javascript
delay = 0.05;   // 秒，每层延迟
idx = index - 1;
thisComp.layer(1).position.valueAtTime(time - delay * idx)
```

**Canvas 等价：**
```javascript
function staggeredValue(elements, time, delayPerElement, valueFn) {
  return elements.map((el, i) => {
    const localTime = Math.max(0, time - i * delayPerElement);
    return valueFn(localTime);
  });
}
// 风铃的每条链用不同的 delay：
// angle[i] = swingFn(time - i * 0.08)
```

**推荐参数：**
- 快速波浪（文字逐个出现）：30-60ms/元素
- 柔和波浪（风吹过）：80-150ms/元素
- 慢速级联（多米诺）：200-400ms/元素

---

## 7. 缓动函数对照表

AE 的速度图编辑器本质是贝塞尔曲线。常用曲线：

| 名称 | 贝塞尔参数 | 用途 | 感觉 |
|------|-----------|------|------|
| ease-out（减速入场） | (0, 0, 0.2, 1) | 元素进入画面 | 快速到达然后柔和停下 |
| ease-in（加速退场） | (0.4, 0, 1, 1) | 元素离开画面 | 慢启动然后加速飞走 |
| ease-in-out（两头慢中间快） | (0.4, 0, 0.2, 1) | 位移/缩放 | 平滑自然 |
| overshoot | (0.34, 1.56, 0.64, 1) | 弹入 | 超过目标再弹回 |
| sharp-in | (0.5, 0, 0.75, 0) | 快速退场 | 急加速冲出去 |
| gentle-out | (0.1, 0, 0.3, 1) | 柔和入场 | 几乎匀速到达，轻柔停下 |

**Canvas 实现：**
```javascript
function cubicBezier(p1x, p1y, p2x, p2y) {
  // 返回一个 t(0-1) → value(0-1) 的函数
  // 用牛顿迭代法求解
  return function(t) {
    let x = t, i = 0;
    while (i++ < 8) {
      const cx = 3*p1x*(1-x)*(1-x)*x + 3*p2x*(1-x)*x*x + x*x*x - t;
      const dx = 3*p1x*(1-2*x)*(1-x) + 3*p2x*(2*x-x*x-x) + 3*x*x;
      x -= cx / dx;
    }
    return 3*p1y*(1-x)*(1-x)*x + 3*p2y*(1-x)*x*x + x*x*x;
  };
}
// const easeOut = cubicBezier(0, 0, 0.2, 1);
// const progress = easeOut(elapsed / duration);
```

---

## 8. 路径跟随（Path Follow）

物体沿曲线运动，朝向自动对齐运动方向。

**Canvas 等价：**
```javascript
function followPath(points, t) {
  // t: 0-1 进度
  // points: [{x,y}, ...] 路径控制点
  // 返回 { x, y, angle }
  const idx = Math.min(Math.floor(t * (points.length - 1)), points.length - 2);
  const localT = (t * (points.length - 1)) - idx;
  const p0 = points[idx], p1 = points[idx + 1];
  const x = p0.x + (p1.x - p0.x) * localT;
  const y = p0.y + (p1.y - p0.y) * localT;
  const angle = Math.atan2(p1.y - p0.y, p1.x - p0.x);
  return { x, y, angle };
}
```

---

## 使用建议

1. **不要从头推导**——先从这个表里找最接近的模式，调参数适配
2. **组合使用**——弹跳 + 衰减摆动 = 落地后晃动；惯性 + ease-out = 自然停止
3. **参数调整原则**：先用推荐值跑一遍看效果，再微调
4. **帧率无关**：所有公式基于时间（秒），不基于帧数，在任何帧率下行为一致
