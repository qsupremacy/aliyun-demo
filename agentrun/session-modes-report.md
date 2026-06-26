# 会话模式对比报告：Isolation vs Sharing

> 数据源：`agentrun/isolation.log`、`agentrun/same.log`、`agentrun/diff.log`（各 800 行）
> 框架：基于 `same.log × diff.log` 的会话共享模式，与 `isolation.log` 的会话隔离模式做对比
> 仅使用上述三份日志的当前数据

---

## 1. 三种模式总览

| 维度 | isolation.log | same.log | diff.log |
|---|---|---|---|
| 跑测时间 | 10:01:07 → 10:14:28 | 09:44:24 → 09:44:32 | 09:41:22 → 09:41:30 |
| 持续时长 | **13 分 21 秒** | **8 秒** | **8 秒** |
| 请求数 | 100 | 100 | 100 |
| 唯一 session | 100（每个 uuid） | 1（haolipeng 复用） | 100（每个 uuid） |
| 唯一主机名 | **100（每请求一个新 pod）** | 1（同一 pod） | 1（同一 pod） |
| invocation_id 范围 | **100 次都是 #1** | #201 ~ #300 | #101 ~ #200 |
| 平均 elapsed | **8006 ms** | 81 ms | 77 ms |
| 平均 QPS | ~0.12 | ~12.5 | ~12.5 |

**模式差异一句话总结**：isolation 模式下，每次请求都起一个全新的 pod 独立服务；sharing 模式下，所有请求打到同一个 pod 上复用进程状态。

---

## 2. Isolation 模式详解

### 2.1 资源分配

100 个请求 → **100 个不同 pod**：

```
request  1  →  c-6a3ddd63-16d705c2-b30b7d62c854 #1
request  5  →  c-6a3ddd8c-16d705c2-18d99c59fdd7 #1
request 10  →  c-6a3dddbb-16d705c2-2c8770db6109 #1
request 50  →  c-6a3ddf13-16d705c2-f876eecb54c9 #1
request 99  →  c-6a3de072-16d705c2-bd18d2cfdd42 #1
request 100 →  c-6a3de07a-16d705c2-95bec047dc1d #1
```

每个 pod 的主机名前 8 位都不同（`c-6a3ddd63` → `c-6a3ddd6d` → `c-6a3ddd77` → ...），但中段 `16d705c2` 一致 —— 推测都是同一台 K8s node / ECS 实例上临时创建的容器。

### 2.2 invocation_id 全部归零

```
invocation_id 分布: 100 × #1
```

**所有 100 次响应的 invocation_id 都是 #1**。这印证了 isolation 的设计：每个 pod 是新进程，`_invocation_counter` 初始值是 0，第一次自增后变 1。

对比 sharing 模式（same.log 的 #201~#300、diff.log 的 #101~#200），counter 严格在同一个 pod 进程内持续累加。

### 2.3 延迟分布

| 指标 | isolation | same | diff |
|---|---|---|---|
| 最小 | 2181 ms | 66 ms | 66 ms |
| p50 | 8973 ms | 76 ms | 75 ms |
| 平均 | 8006 ms | 81 ms | 77 ms |
| p90 | 10148 ms | 91 ms | 88 ms |
| p99 | 11365 ms | 191 ms | 123 ms |
| 最大 | 11365 ms | 191 ms | 123 ms |

isolation 模式下**没有任何一次请求快于 2 秒**。最小值 2181ms 已经比 sharing 模式的最大值（191ms）高一个数量级。

---

## 3. 三模式性能差异

### 3.1 延迟倍率

以 sharing 模式（diff.log）的平均 77ms 为基准：

| 模式 | 平均延迟 | 倍率 |
|---|---|---|
| sharing (diff) | 77 ms | 1.0× |
| sharing (same) | 81 ms | 1.05× |
| **isolation** | **8006 ms** | **104×** |

isolation 模式比 sharing 模式**慢约 100 倍**。

### 3.2 延迟主要构成

isolation 的 ~8 秒响应时间几乎全部花在：
- 新 pod 调度 / 镜像拉取 / 容器启动
- 进程初始化（导入 langchain、pydash、agentrun 等重依赖）
- 第一次 invoke 前的环境准备

sharing 模式没有这部分开销 —— pod 已就绪，进程已 warmup，counter 已在内存里。

### 3.3 长尾特征

| 模式 | max / p99 | 形态 |
|---|---|---|
| isolation | 11365 / 11365 ms | max = p99，单点长尾 |
| same | 191 / 191 ms | max = p99，单点抖动 |
| diff | 123 / 123 ms | max = p99，单点抖动 |

三种模式都是 max = p99，意味着都是单点慢请求拉起尾巴，不是系统性的长尾分布。isolation 的长尾是容器启动时间的方差（最快 2s、最慢 11s），sharing 的长尾是单次内部抖点。

---

## 4. 路由与会话语义

### 4.1 routing 行为

| 模式 | 同一 session 多次请求会路由到 | 不同 session 请求会路由到 |
|---|---|---|
| isolation | **不同 pod**（每次新容器） | 各自独立 pod |
| sharing (same) | 同一 pod | 不适用（只有 1 个 session） |
| sharing (diff) | 不适用（无 session 复用） | 同一 pod |

isolation 的"会话隔离"是**基础设施层面**的隔离 —— 每次请求都是独立的 OS 进程；sharing 的"会话"是**进程内状态**的复用，所有请求共享同一个进程的内存和 counter。

### 4.2 数据完整性

| 检查项 | isolation | same | diff |
|---|---|---|---|
| 响应格式合规 | 100/100 | 100/100 | 100/100 |
| 流式 `[DONE]` 收尾 | 100/100 | 100/100 | 100/100 |
| HTTP 5xx | 0 | 0 | 0 |
| 编号乱序 | 0 | 0 | 0 |
| 异常中断 | 0 | 0 | 0 |

三份日志 0 异常，三种模式在功能正确性上无差异。

---

## 5. 关键发现

1. **Isolation 模式每次请求都新建容器**：100 个请求 = 100 个不同 pod，每个 pod 自己的 invocation_id 从 #1 开始
2. **Isolation 比 Sharing 慢 ~100 倍**：8 秒 vs 80 毫秒，差距主要来自容器启动 + 进程初始化
3. **Sharing 模式会话复用是 in-process 的**：counter 在模块级全局变量上累加，跨请求持久
4. **不同模式的语义对比**：
   - **isolation** 适合"高安全隔离 / 多租户强隔离"场景 —— 每次都是新进程，状态零共享，但贵
   - **sharing** 适合"低延迟高吞吐"场景 —— 复用进程状态，便宜但所有 session 共享底层资源
5. **中间段 `16d705c2` 在所有模式中都是同一台物理节点**：无论 1 个 pod 还是 100 个 pod，都跑在同一台 K8s node / ECS 上
6. **mock agent 模式下延迟差异完全由"进程生命周期"决定**：跟 session 字段、模型推理都无关，纯基础设施差异

---

## 6. 模式选型建议

| 场景 | 推荐模式 | 理由 |
|---|---|---|
| 内部测试 / dev | sharing | 快，~80ms 一轮 |
| 外部服务 / SaaS | sharing + 细粒度 auth | 延迟敏感 |
| 多租户 / 客户数据强隔离 | isolation | 合规要求 |
| 调试复杂 session 状态污染 | isolation | 每次新进程天然排除状态污染 |
| 压测基线 | sharing | 排除冷启动干扰，看真实稳态 |

---

## 7. 局限

- **样本量**：每个模式仅 100 次请求，p99 等于 max 意味着极小样本下没法区分长尾和单点抖动
- **mock agent**：当前 main.py 走的是 mock 分支，真实 LLM 推理下两种模式的延迟差距会缩小（启动开销占比下降）
- **不涉及并发**：三份日志都是串行（curl 无 `&`），isolation 模式的 100 个 pod 实际是顺序启动的；如果并发 100 个 isolation 请求，总时长会接近 max 而不是 sum
- **未观测到的模式**：没有"sharing 但每个 session 限速"、"isolation 但 pod 池化预热"等混合模式数据
- **没看到冷启动 vs 暖机**：isolation 模式下"启动开销"是每个请求都要付的代价，所以没机会观察稳态

---

## 附录 A：脚本与日志对应

- `isolation.sh`（待确认文件名）→ `isolation.log`（每请求新 session + 新 pod）
- `same.sh` → `same.log`（固定 session，共享 pod）
- `diff.sh` → `diff.log`（每请求新 session，共享 pod）

## 附录 B：延迟倍数对照

```
isolation p50  8973 ms  ┃■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■
same     p50    76 ms  ┃■
diff     p50    75 ms  ┃■
```

sharing 比 isolation 快约 **118 倍**（p50 比值）。
