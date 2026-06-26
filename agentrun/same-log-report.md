# same.log × diff.log 对比报告

> 数据源：`agentrun/same.log`（800 行）、`agentrun/diff.log`（800 行）
> 仅基于这两份日志的当前数据生成，不引用历史跑测。
> 同一份 `main.py` mock agent（HOSTNAME 来自环境），同一个压测脚本骨架。

---

## 1. 数据集速览

| 维度 | same.log | diff.log |
|---|---|---|
| 跑测时间窗 | 09:44:24 → 09:44:32（8s） | 09:41:22 → 09:41:30（8s） |
| 请求数 | 100 | 100 |
| 唯一 session 数 | **1**（`haolipeng`，100% 复用） | **100**（每次 uuidgen 新值） |
| 唯一主机名 | 1 个：`c-6a3dd7d1-16d705c2-d3adf36fe443` | 1 个：`c-6a3dd7d1-16d705c2-d3adf36fe443` |
| invocation_id 范围 | #201 ~ #300 | #101 ~ #200 |
| invocation_id 缺号 | 无 | 无 |
| invocation_id 重复 | 0 | 0 |
| 平均 elapsed | 81.3 ms | 77.0 ms |

两份日志唯一**实质性**差异：session 处理方式（100% 复用 vs 100% 唯一）。

---

## 2. invocation_id 与跑测顺序

| 文件 | 时间 | invocation_id 区间 |
|---|---|---|
| diff.log  | 09:41 起 | #101 ~ #200 |
| same.log | 09:44 起 | #201 ~ #300 |

`request N → invocation_id` 严格对应（`invocation_id = request_index + 区间起点`），抽样验证：

| 文件 | req 1 | req 10 | req 50 | req 100 |
|---|---|---|---|---|
| diff.log  | #101 | #110 | #150 | #200 |
| same.log | #201 | #210 | #250 | #300 |

diff.log（09:41 跑）的最大值 #200 正好衔接 same.log（09:44 跑）的起始值 #201 —— **counter 跨跑测持续累加，agent 容器进程未重启**。

---

## 3. 响应耗时分布

| 指标 | same.log（固定 session） | diff.log（每请求新 session） |
|---|---|---|
| 最小 | 66 ms | 66 ms |
| p50 | 76 ms | 75 ms |
| 平均 | 81.3 ms | 77.0 ms |
| p90 | 91 ms | 88 ms |
| p99 | 191 ms | 123 ms |
| 最大 | 191 ms | 123 ms |
| 总耗时 | 8.132 s | 7.699 s |

### 分布观察

- **主体几乎重合**：两份日志的 min/p50/avg/p90 都在 66~91ms 区间，差异在噪声范围内
- **尾巴差异**：same.log 的 p99 是 191ms，diff.log 是 123ms，但 same.log 的 max 恰好也是 191ms，**整条尾巴被一个孤立的慢请求拉起来**
- 看 max = p99 的现象，说明 same.log 里只有尾部 1~2 个请求异常慢

---

## 4. same.log 的尾部异常

为验证 p99/max = 191ms 的成因：

| 区间 | 区间内 elapsed |
|---|---|
| 前 50 个请求 | avg ~77ms（和 diff.log 一致） |
| 后 50 个请求 | 出现 1~2 个 ~190ms 的离群点 |

same.log 不是整体变慢，而是尾部有偶发抖动。这种长尾在 mock 模式下通常来自：
- 第一次写满 socket buffer 的瞬时阻塞
- 日志系统（写文件）某次 fsync 抖了一下
- 同 pod 上其它工作负载抢占 CPU（虽然 mock agent 不消耗 LLM，但 AgentRun runtime 本身可能有周期任务）

差异**不**能用"session 切换开销"解释 —— session 切换只发生在 diff.log（每次都建新 session），反而 diff.log 更稳。

---

## 5. 主机名一致性

两份日志 100% 的响应都来自同一个 pod：

```
c-6a3dd7d1-16d705c2-d3adf36fe443
```

意味着：
- 两次跑测的请求都命中了同一个 agent 实例
- 没有观察到负载均衡到多 pod 的现象
- **LB 配置 / 路由策略**：要么只有一个 pod 在服务，要么 LB 是 sticky 的（按 header 哈希到了这一个 pod），从 200 次请求的结果看更像是单 pod 情况

---

## 6. 数据质量

| 检查项 | same.log | diff.log |
|---|---|---|
| 响应格式合规 | 100/100 | 100/100 |
| invocation_id 唯一 | 100/100 | 100/100 |
| session 行为符合预期 | ✅ 100% 复用 | ✅ 100% 唯一 |
| 流式 `[DONE]` 收尾 | 100/100 | 100/100 |
| HTTP 5xx | 0 | 0 |
| 编号乱序 | 0 | 0 |

**两份日志 0 异常。**

---

## 7. 关键发现

1. **session 复用 vs 每次新建，对 mock agent 延迟无可见影响** —— 两份日志平均 77 vs 81 ms 差 4ms，在同 pod 同负载下属于噪声
2. **counter 是进程级状态，跨跑测持久化** —— #200 → #201 无缝衔接，验证了 main.py 里 `_invocation_counter` 是模块级全局
3. **当前部署是单 pod** —— 200 次请求 0 次命中其它实例
4. **mock agent 的稳态基线 ≈ 80ms** —— p50 在 75ms，p90 在 90ms 内
5. **存在偶发长尾（~190ms）** —— 在 same.log 尾部被观测到一次，p99 = max 的形态说明是单点抖动而非系统性问题

---

## 8. 局限 / 没回答的问题

- **本报告数据是 mock 模式**，没有 LLM 推理、工具调用、沙箱等真实负载
- **本报告是串行跑测**（curl 没 `&`），无法评估并发性能
- **只跑了一个 pod**，多 pod 之间的性能差异未知
- **样本量 100 + 100 = 200**，p99/max 估算置信度有限（100 个样本的 p99 实际上就是最大值）
- **没有错误注入**，故障路径下的行为没覆盖
- **跑测间隔 ~3 分钟**，冷启动影响已被前 100 次请求暖掉，**没有冷启动基线**

---

## 附录 A：抽样对照

| request # | diff.log 响应 | same.log 响应 |
|---|---|---|
| 1   | c-6a3dd7d1-... #101 | c-6a3dd7d1-... #201 |
| 10  | c-6a3dd7d1-... #110 | c-6a3dd7d1-... #210 |
| 50  | c-6a3dd7d1-... #150 | c-6a3dd7d1-... #250 |
| 100 | c-6a3dd7d1-... #200 | c-6a3dd7d1-... #300 |

## 附录 B：脚本与日志的对应

- `same.sh` 跑 → `same.log`（固定 session）
- `diff.sh` 跑 → `diff.log`（每次新 session）
