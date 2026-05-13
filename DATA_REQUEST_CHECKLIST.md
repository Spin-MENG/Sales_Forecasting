# 新品销量预测数据清单

这份清单用于向同事收集数据。目标是让工具从「本品参数 + 锚点销量纪录」直接完成：

```text
DE 月销预测 -> 全球非美销量预测
```

不要求同事先提供 DE 预测 CSV。DE CSV 只是可选的人工覆盖入口。

## 1. 本品基础信息

| 必填 | 字段 | 示例 | 说明 |
|---|---|---|---|
| 是 | 产品名 | BE10000 | 用于报告标题和输出文件名 |
| 是 | 上市月份 | 2026-07 | 格式 `YYYY-MM` |
| 是 | 品类 | dual_band_wifi7 | 用于产品相似度 |
| 是 | Wi-Fi 标准 | wifi7 | 例如 `wifi6`, `wifi6e`, `wifi7` |
| 是 | 频段 | dual_band | `dual_band` / `tri_band` |
| 是 | 定位 | mid | `entry` / `mid` / `high` |
| 是 | MSRP | 179.99 | 建议用目标市场币种统一口径 |
| 是 | 预计成交均价 | 159.99 | 没有时先填 MSRP |
| 建议 | 目标区域 | DE, EU, UK, AU, CA, JP, ROW | 当前输出是全球非美 |

## 2. 第一层 DE Hybrid 预测资料

第一层用原 BE7200 DE v5.14 方法论：

```text
DE(t) = max(0, [Bass(t) + Opening(t)] × Seasonal[calendar_month]
             + Pulse[calendar_month] × Steady/175) × ratio
```

### 2.1 DE 锚点月销纪录

提供以下两种之一：

| 方式 | 需要提供 |
|---|---|
| 已整理 state JSON | `de_anchors_state.json` 路径 |
| 原始月销表 | 产品 / ASIN、月份、德国 Amazon 月销，AI 可整理成 state JSON |

state JSON 结构：

```json
{
  "anchors": {
    "Flint2": {
      "monthly_de_amazon": {
        "2026-02": 580,
        "2026-03": 662,
        "2026-04": 636
      }
    }
  },
  "competitors_keepa": {
    "B09T9BMKR3": {
      "monthly": {
        "2026-02": 280,
        "2026-03": 310,
        "2026-04": 300
      }
    }
  }
}
```

要求：

- 月份格式为 `YYYY-MM`。
- 每个 DE 稳态锚点最好有最近 6 个月销量。
- 销量口径要统一，例如都为 Germany Amazon 月销。
- 竞品如果来自 Keepa 或估算，需要标注来源。

### 2.2 DE 稳态锚点表

每个锚点需要提供：

| 必填 | 字段 | 示例 | 说明 |
|---|---|---|---|
| 是 | `label` | Flint 2 (MT6000) | 展示名 |
| 是 | `key` | Flint2 | 对应 state JSON 里的 key |
| 是 | `source` | anchors | `anchors` 或 `competitors` |
| 是 | `weight` | 0.55 | 稳态权重 |
| 是 | `v1_factor` | 1.18 | 悲观档相对系数 |
| 是 | `v2_factor` | 1.25 | 中性档相对系数 |
| 是 | `v3_factor` | 1.35 | 乐观档相对系数 |
| 建议 | reason | 直接前代，BE10000 应高于 MT6000 | 方便复核 |

计算口径：

```text
Steady(v) = Σ weight(i) × recent_avg(i) × factor(i, v)
```

检查项：

- `weight` 合计建议约等于 1。
- 主锚点必须有清楚业务理由，例如直接前代、同价位竞品、同代高端参考。
- V1/V2/V3 factor 要符合业务直觉：`v1_factor <= v2_factor <= v3_factor`。

## 3. 第二层全球非美反推资料

第二层需要历史产品的区域销量 Excel，用来计算：

```text
Global ex-US(t) = DE(t) × (DE / 非美占比)^-1
```

### 3.1 区域销量 Excel

每个锚点产品一个 Excel，默认 sheet 名为 `销量`。

必须包含：

| 必填 | 字段 | 示例 | 说明 |
|---|---|---|---|
| 是 | 国家 | 德国 | 国家名称 |
| 是 | 店铺 | Amazon DE | 渠道 / 店铺 |
| 是 | 月份列 | 2026-01 | 多个月份列，格式 `YYYY-MM` |

要求：

- 德国销量必须存在，否则无法计算 DE/非美占比。
- 美国销量不是必需；没有美国数据时工具会按无美国数据继续计算。
- 月份列必须连续。
- 至少提供 2 个全球区域锚点产品。

### 3.2 全球区域锚点产品信息

每个锚点需要提供：

| 必填 | 字段 | 示例 | 说明 |
|---|---|---|---|
| 是 | `name` | MT6000_recent | 锚点 ID |
| 是 | `file` | MT6000_sales.xlsx | 区域销量 Excel 文件名 |
| 是 | `category` | dual_band_wifi6 | 品类 |
| 是 | `wifi_standard` | wifi6 | Wi-Fi 标准 |
| 是 | `band_type` | dual_band | 频段 |
| 是 | `positioning` | mid | 定位 |
| 是 | `avg_price` | 139.99 | 历史成交均价 |
| 是 | `role` | direct_predecessor_recent | 锚点角色 |
| 是 | `data_source` | internal_sales | 数据来源 |
| 是 | `start_month` | 2025-11 | 使用窗口开始 |
| 是 | `end_month` | 2026-04 | 使用窗口结束 |
| 是 | `weight` | 0.5 | 手动权重；auto 模式也会展示 |

常用 `role`：

```text
direct_predecessor_recent
direct_predecessor_history
same_generation
same_generation_high_end
adjacent_reference
competitor
```

常用 `data_source`：

```text
internal_sales
seller_central
keepa_estimate
manual_estimate
```

## 4. 可选资料

| 资料 | 什么时候需要 |
|---|---|
| DE 预测 CSV | 已有人手校准后的 DE 月度预测，想跳过 Hybrid DE 第一层 |
| 自定义 Bass 参数 | 新品扩散节奏明显不同于 BE7200 |
| 自定义 Seasonal / Pulse | 品类季节性或促销节奏不同 |
| 已知营销节点 | 需要解释某些月份的峰值或低谷 |

DE CSV 格式：

```csv
M,cal,V1_low,V1_mid,V1_high,V2_low,V2_mid,V2_high,V3_low,V3_mid,V3_high
1,2026-07,300,355,410,330,385,440,360,424,488
```

## 5. 交付给 AI 时的最小包

把下面内容发给 Claude / Codex 即可：

```text
请用 Sales_Forecasting 工具跑新品预测。

资料包：
1. 本品基础信息：<粘贴或给文件路径>
2. DE 锚点月销纪录：<state JSON 路径或原始月销表路径>
3. DE 稳态锚点表：<粘贴表格>
4. 全球区域销量 Excel 目录：<路径>
5. 全球区域锚点产品信息：<粘贴表格>
6. 输出目录：<路径>

要求：
- 默认使用 hybrid_de，不要要求我先提供 DE 预测 CSV。
- 先检查资料是否完整；缺关键数据就明确列出。
- 生成本地 config 后运行工具。
- 不要提交真实数据、真实 config 或生成报告。
- 最后汇总 DE 和全球非美的 Y1 / M18 / 峰值月 / P10-P50-P90。
```

## 6. 不要提交到 Git 的内容

- 真实销量 Excel。
- 真实 DE state JSON。
- 真实产品 config。
- 生成的 CSV / PNG / HTML / Markdown 报告。
- 含价格、销量、ASIN 组合的内部敏感文件。
