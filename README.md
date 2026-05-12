# Sales Forecasting Tool

新品销量预测工具。它把一个核心市场的 DE 月度预测，结合历史锚点产品的 `DE / 非美` 区域占比，生成全球非美销量预测、P10/P50/P90 风险区间、图表和报告。

这个 repo 只放工具代码和配置模板，不应该上传内部销量 Excel、真实产品配置、生成后的 CSV/HTML/Markdown 报告。

## 适合谁用

适合需要预测新品销量的同事：

- 已经有一个产品的 DE 月度预测 CSV。
- 手上有 2 个或以上历史锚点产品的区域销量 Excel。
- 想快速得到全球非美销量、P10/P50/P90、峰值月、Y1/M18 累计和一份可汇报的说明。

## 你需要准备什么

### 1. DE 预测 CSV

当前工具默认读取 18 个月预测，CSV 至少要有这些列位顺序：

```text
M, cal,
v1_low, v1_mid, v1_high,
v2_low, v2_mid, v2_high,
v3_low, v3_mid, v3_high
```

实际字段名不严格依赖表头，脚本按列位置读取。推荐保留表头，便于人工检查。

示例行：

```csv
M,cal,v1_low,v1_mid,v1_high,v2_low,v2_mid,v2_high,v3_low,v3_mid,v3_high
1,2026-07,300,355,410,330,385,440,360,424,488
```

### 2. 锚点产品销量 Excel

每个锚点产品一个 Excel，工作表默认叫 `销量`。

必须包含：

| 字段 | 说明 |
|---|---|
| `国家` | 国家名称，例如 `德国`、`美国`、`英国` |
| `店铺` | 店铺或渠道名称 |
| `YYYY-MM` 月份列 | 例如 `2026-01`, `2026-02` |

要求：

- 月份列必须连续。
- 德国销量必须存在，因为当前模型依赖 DE/非美占比。
- 美国销量不是必需的。没有美国数据时，工具会按“无美国数据”继续计算。
- 锚点产品至少 2 个。

### 3. 产品信息

目标产品和每个锚点产品都需要：

| 字段 | 用途 |
|---|---|
| `name` | 产品名 |
| `category` | 品类相似度 |
| `wifi_standard` | Wi-Fi 标准相似度 |
| `band_type` | 双频 / 三频相似度 |
| `positioning` | 入门 / 中端 / 高端定位 |
| `msrp` 或 `expected_avg_price` / `avg_price` | 价格相似度 |

## 第一次怎么跑

### 1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 复制配置模板

```bash
cp forecast_config_template.yaml my_product_config.yaml
```

填写：

- `paths.output_dir`
- `paths.base_data_dir`
- `paths.de_forecast_csv`
- `output.prefix`
- `output.version_slug`
- `target_product`
- `anchor_products`

### 3. 运行预测

```bash
python3 forecast_tool.py --config my_product_config.yaml
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

## 常见校验错误

工具会尽量输出业务语言，而不是 Python traceback。

示例：

```text
配置校验未通过：
- MT6000 文件中没有德国销量，无法计算 DE/非美占比。
```

其他会检查：

- 月份是否连续。
- 是否有 `国家` / `店铺`。
- 德国销量是否存在。
- 锚点是否少于 2 个。
- 价格、品类、Wi-Fi 标准是否缺失。
- DE/非美占比是否异常。

## 怎么让 AI 帮你调用

你可以把下面这段发给 Claude / Codex：

```text
请使用这个 repo 的 Sales Forecasting Tool 帮我跑新品预测。

我的输入：
1. DE 预测 CSV：<填文件路径>
2. 锚点销量 Excel 目录：<填目录路径>
3. 输出目录：<填输出目录>
4. 目标产品：
   - name:
   - category:
   - launch_date:
   - msrp:
   - expected_avg_price:
   - wifi_standard:
   - band_type:
   - positioning:
5. 锚点产品列表：
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

请你：
1. 复制 forecast_config_template.yaml 生成一个新 config。
2. 填入上述信息。
3. 运行 python3 forecast_tool.py --config <config path>。
4. 如果报错，请根据业务校验信息修复 config 或指出缺少什么数据。
5. 最后总结 P10/P50/P90、Y1、M18、峰值月，并列出输出文件路径。
```

## AI Agent 操作规范

给 Claude / Codex 使用时，建议要求它遵守：

- 不要上传或提交真实 Excel、CSV、HTML、PNG、Markdown 预测结果。
- 真实业务配置文件也不要提交。
- 只修改模板、代码、README 或测试文件。
- 跑完后要对比核心数字，确认改动没有意外改变模型口径。

## 当前模型边界

当前版本是：

```text
Global ex-US(t) = DE forecast(t) × multiplier
```

其中 multiplier 来自历史锚点产品的 `DE / 非美` 占比，并用 Monte Carlo 输出 P10/P50/P90。

尚未建模：

- 独立区域拆分，例如 UK / CA / AU / JP / ROW。
- 价格折扣、广告预算、评论数、评分、库存约束。
- DE 预测本身误差。

这些可以作为后续版本继续扩展。

