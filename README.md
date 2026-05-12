# Sales Forecasting Tool

新品销量预测工具。它不是要求你先准备 DE 预测 CSV；正常流程是输入本品参数、DE 锚点销量纪录、全球区域锚点销量 Excel，工具自动完成两层预测：

```text
[第一层] 本品 DE 月销 = Hybrid DE 模型
         steady anchors × Bass × Opening × Seasonal/Pulse

[第二层] 本品全球非美月销 = DE 月销 × (DE / 非美占比)^-1
         基于历史锚点产品的区域销量反推
```

`de_forecast_csv` 只保留为可选入口：如果你已经有人手校准后的 DE 月度预测，可以跳过第一层直接接入。

这个 repo 只放工具代码和配置模板，不应该上传内部销量 Excel、真实产品配置、生成后的 CSV/HTML/Markdown 报告。

## 同事需要准备什么

### 1. 本品参数

填在 `target_product`：

| 字段 | 说明 |
|---|---|
| `name` | 新品名 |
| `launch_date` | 上市月份，例如 `2026-07` |
| `category` | 品类，用于锚点相似度 |
| `wifi_standard` | Wi-Fi 标准，例如 `wifi7` |
| `band_type` | 双频 / 三频 |
| `positioning` | 入门 / 中端 / 高端 |
| `msrp` / `expected_avg_price` | 定价口径 |

### 2. DE 锚点销量纪录

第一层 Hybrid DE 模型需要一份 `de_anchors_state.json`。结构参考：

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

在 `de_forecast_model.steady_anchors` 里说明每个锚点怎么用：

| 字段 | 说明 |
|---|---|
| `label` | 展示名 |
| `key` | 对应 state JSON 里的产品名或 ASIN |
| `source` | `anchors` 或 `competitors` |
| `weight` | 稳态权重 |
| `v1_factor` / `v2_factor` / `v3_factor` | 本品相对该锚点的三档系数 |

第一层会用近 `recent_n` 个月均值计算：

```text
Steady(v) = Σ weight(i) × recent_avg(i) × factor(i, v)
```

再用 BE7200 v5.14 方法论里的 Bass、Opening、Seasonal、Pulse 生成 M1-M18 的 DE 月度三档。

### 3. 全球区域锚点销量 Excel

第二层全球非美反推需要每个锚点产品一个 Excel，默认工作表叫 `销量`。

必须包含：

| 字段 | 说明 |
|---|---|
| `国家` | 国家名称，例如 `德国`、`美国`、`英国` |
| `店铺` | 店铺或渠道名称 |
| `YYYY-MM` 月份列 | 例如 `2026-01`, `2026-02` |

要求：

- 月份列必须连续。
- 德国销量必须存在，因为模型依赖 DE/非美占比。
- 美国销量不是必需的。没有美国数据时，工具会按“无美国数据”继续计算。
- 区域锚点产品至少 2 个。

这些 Excel 填在 `anchor_products`，用于计算历史 `DE / 非美` 占比和 multiplier。

## 第一次怎么跑

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp forecast_config_template.yaml my_product_config.yaml
python3 forecast_tool.py --config my_product_config.yaml
```

需要填写：

- `paths.output_dir`
- `paths.base_data_dir`
- `target_product`
- `de_forecast_model.state_json`
- `de_forecast_model.steady_anchors`
- `anchor_products`

如果你已经有 DE 预测 CSV，把配置改成：

```yaml
paths:
  de_forecast_csv: /path/to/de_forecast.csv

de_forecast_model:
  mode: csv
```

## 输出什么

假设配置是：

```yaml
output:
  prefix: be10000_global_ex_us
  version_slug: v1_0
```

会输出：

```text
be10000_global_ex_us_forecast_v1_0.csv
be10000_global_ex_us_charts_v1_0.png
be10000_global_ex_us_method_v1_0.md
be10000_global_ex_us_executive_summary_v1_0.md
be10000_global_ex_us_interactive_v1_0.html
```

管理层常用口径：

| 口径 | 用途 |
|---|---|
| P10 | 保守备货线 |
| P50 | 中性经营线 |
| P90 | 产能 / 断货风险线 |

## 怎么让 AI 帮你调用

把下面这段发给 Claude / Codex：

```text
请使用这个 repo 的 Sales Forecasting Tool 帮我跑新品预测。

我的输入：
1. 本品参数：
   - name:
   - launch_date:
   - category:
   - msrp:
   - expected_avg_price:
   - wifi_standard:
   - band_type:
   - positioning:
2. DE 锚点 state JSON：<填路径>
3. DE 稳态锚点表：
   - label:
     key:
     source: anchors / competitors
     weight:
     v1_factor:
     v2_factor:
     v3_factor:
4. 全球区域锚点 Excel 目录：<填路径>
5. 全球区域锚点产品列表：
   - name:
     file:
     category:
     wifi_standard:
     band_type:
     positioning:
     avg_price:
     role:
     data_source:
     start_month:
     end_month:
     weight:
6. 输出目录：<填路径>

请你：
1. 复制 forecast_config_template.yaml 生成一个新 config。
2. 填入上述信息，默认使用 de_forecast_model.mode=hybrid_de。
3. 运行 python3 forecast_tool.py --config <config path>。
4. 如果报错，请根据业务校验信息修复 config 或指出缺少什么数据。
5. 最后总结 DE V1/V2/V3、全球非美 P10/P50/P90、Y1、M18、峰值月，并列出输出文件路径。
```

## 常见校验错误

工具会尽量输出业务语言，而不是 Python traceback。

示例：

```text
配置校验未通过：
- MT6000 文件中没有德国销量，无法计算 DE/非美占比。
```

还会检查：

- DE hybrid 是否有 state JSON、launch month、steady anchors。
- 区域 Excel 月份是否连续。
- 是否有 `国家` / `店铺`。
- 德国销量是否存在。
- 区域锚点是否少于 2 个。
- 价格、品类、Wi-Fi 标准是否缺失。
- DE/非美占比是否异常。

## AI Agent 操作规范

给 Claude / Codex 使用时，建议要求它遵守：

- 不要上传或提交真实 Excel、CSV、HTML、PNG、Markdown 预测结果。
- 真实业务配置文件和 state JSON 也不要提交。
- 只修改模板、代码、README 或测试文件。
- 跑完后要对比核心数字，确认改动没有意外改变模型口径。

## 当前模型边界

第一层 DE：

```text
DE(t) = max(0, [Bass(t) + Opening(t)] × Seasonal[calendar_month]
             + Pulse[calendar_month] × Steady/175) × ratio
```

第二层全球非美：

```text
Global ex-US(t) = DE(t) × multiplier
```

尚未建模：

- 独立区域拆分，例如 UK / CA / AU / JP / ROW。
- 价格折扣、广告预算、评论数、评分、库存约束。
- DE 锚点 state JSON 的自动清洗生成。
