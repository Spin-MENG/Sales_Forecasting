import csv
import html as html_lib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .explain import generate_explanation_points

plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Arial Unicode MS', 'Heiti TC']
plt.rcParams['axes.unicode_minus'] = False


def slugify_version(version):
    return str(version or "v1").strip().lower().replace(".", "_").replace("-", "_")


def get_output_settings(config, target_product):
    output = config.get("output", {})
    forecast = config.get("forecast", {})
    product_name = target_product.get("name") or forecast.get("product") or "target_product"
    default_prefix = f"{product_name.lower()}_global_ex_us"
    prefix = output.get("prefix", default_prefix)
    version_slug = output.get("version_slug") or slugify_version(forecast.get("version", "v1"))
    de_source_label = forecast.get("de_source_label")
    if not de_source_label:
        mode = str(config.get("de_forecast_model", {}).get("mode", "")).lower()
        de_source_label = "Hybrid DE" if mode == "hybrid_de" else "DE input"
    return {
        "prefix": prefix,
        "version_slug": version_slug,
        "de_source_label": de_source_label,
    }


def build_output_paths(output_dir, output_settings):
    output_dir = Path(output_dir)
    return {
        "csv": output_dir / f"{output_settings['prefix']}_forecast_{output_settings['version_slug']}.csv",
        "charts_png": output_dir / f"{output_settings['prefix']}_charts_{output_settings['version_slug']}.png",
        "method_md": output_dir / f"{output_settings['prefix']}_method_{output_settings['version_slug']}.md",
        "summary_md": output_dir / f"{output_settings['prefix']}_executive_summary_{output_settings['version_slug']}.md",
        "interactive_html": output_dir / f"{output_settings['prefix']}_interactive_{output_settings['version_slug']}.html",
    }


def write_reports(
*,
    OUT,
    CONFIG_PATH,
    WEIGHT_MODE,
    manual_mult_mid,
    auto_mult_mid,
    mid_de_pct_non_us,
    share_points,
    mult_low,
    mult_mid,
    mult_high,
    mult_p10,
    mult_p50,
    mult_p90,
    N_MONTE_CARLO,
    RANDOM_SEED,
    de_forecast,
    g_v2_low,
    g_v2_mid,
    g_v2_high,
    g_v2_p10,
    g_v2_p50,
    g_v2_p90,
    g_v1_mid,
    g_v3_mid,
    product_results,
    ANCHOR_PRODUCTS,
    anchor_scores,
    CONFIG,
    TARGET_PRODUCT,
    REGIONS,
    TIMELINE_EVENTS,
    manual_mid_de_pct_non_us,
    auto_mid_de_pct_non_us,
    mult_dist,
    low_share_point,
    high_share_point,
    output_paths,
    de_source_label,
):
    out_csv = output_paths["csv"]
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([f"# {TARGET_PRODUCT.get('name', 'Target Product')} Global ex-US Forecast {CONFIG['forecast'].get('version', 'unknown')}"])
        w.writerow([f"# Based on {de_source_label} DE forecast x DE-to-non-US-global multiplier"])
        weight_text = ", ".join(f"{p['label']} {p['weight']:.2f}" for p in share_points)
        w.writerow([f"# Config = {CONFIG_PATH}"])
        w.writerow([f"# Anchor weight mode = {WEIGHT_MODE}"])
        w.writerow([f"# Manual mid mult = {manual_mult_mid:.2f}x, auto mid mult = {auto_mult_mid:.2f}x"])
        w.writerow([f"# DE/non-US weighted = {mid_de_pct_non_us*100:.2f}% ({weight_text})"])
        w.writerow([f"# Deterministic mult: low={mult_low:.2f}x, mid={mult_mid:.2f}x, high={mult_high:.2f}x"])
        w.writerow([f"# Monte Carlo mult P10/P50/P90: {mult_p10:.2f}x / {mult_p50:.2f}x / {mult_p90:.2f}x (n={N_MONTE_CARLO}, seed={RANDOM_SEED})"])
        w.writerow([])
        w.writerow(["M", "cal", "DE_V2_mid",
                    "Global_V2_low_mult", "Global_V2_mid_mult", "Global_V2_high_mult",
                    "Global_V2_P10_dist", "Global_V2_P50_dist", "Global_V2_P90_dist",
                    "Global_V1_mid_mult", "Global_V3_mid_mult"])
        for i, r in enumerate(de_forecast):
            w.writerow([r['M'], r['cal'], round(r['v2_mid']),
                        round(g_v2_low[i]), round(g_v2_mid[i]), round(g_v2_high[i]),
                        round(g_v2_p10[i]), round(g_v2_p50[i]), round(g_v2_p90[i]),
                        round(g_v1_mid[i]), round(g_v3_mid[i])])
        w.writerow([])
        w.writerow(["cum_Y1", "",
                    round(sum(r['v2_mid'] for r in de_forecast[:12])),
                    round(sum(g_v2_low[:12])), round(sum(g_v2_mid[:12])), round(sum(g_v2_high[:12])),
                    round(sum(g_v2_p10[:12])), round(sum(g_v2_p50[:12])), round(sum(g_v2_p90[:12])),
                    round(sum(g_v1_mid[:12])), round(sum(g_v3_mid[:12]))])
        w.writerow(["cum_M18", "",
                    round(sum(r['v2_mid'] for r in de_forecast)),
                    round(sum(g_v2_low)), round(sum(g_v2_mid)), round(sum(g_v2_high)),
                    round(sum(g_v2_p10)), round(sum(g_v2_p50)), round(sum(g_v2_p90)),
                    round(sum(g_v1_mid)), round(sum(g_v3_mid))])
    print(f"\n写入 {out_csv}")

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    T = len(de_forecast)
    months_idx = list(range(1, T + 1))
    cal_short = [r['cal'][2:] for r in de_forecast]

    ax = axes[0, 0]
    de_v2 = [r['v2_mid'] for r in de_forecast]
    ax.fill_between(months_idx, g_v2_p10, g_v2_p90, alpha=0.18, color='crimson', label='全球非美 V2 (P10~P90 multiplier)')
    ax.plot(months_idx, de_v2, 'o-', color='steelblue', linewidth=2.2, markersize=6, label=f'DE V2 ({de_source_label}, Y1: {sum(de_v2[:12]):.0f})')
    ax.plot(months_idx, g_v2_p50, 's-', color='crimson', linewidth=2.6, markersize=7,
            label=f'全球非美 V2 P50 (Y1: {sum(g_v2_p50[:12]):,.0f})', zorder=5)
    events = [(1, 'M1', 'green'), (5, 'BF Y1', 'red'), (13, 'PD Y2 ★', 'green'), (17, 'BF Y2', 'red')]
    ymax = max(g_v2_p90) * 1.15
    for m, label, color in events:
        ax.axvline(x=m, color=color, linestyle=':', alpha=0.4)
        ax.text(m, ymax*0.97, label, ha='center', fontsize=9, color=color, fontweight='bold')
    ax.set_xticks(months_idx); ax.set_xticklabels(cal_short, rotation=45, fontsize=8)
    ax.set_xlabel('月份'); ax.set_ylabel('月销 (台)')
    ax.set_title(f'{CONFIG["forecast"].get("version", "unknown")} {TARGET_PRODUCT.get("name", "Target Product")} 全球非美 月销 — V2 × multiplier 分布', fontsize=11, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10); ax.grid(True, alpha=0.3); ax.set_ylim(0, ymax)

    ax = axes[0, 1]
    labels = [p["label"].replace("_", "\n") for p in share_points] + ["加权\n综合"]
    values = [p["de_pct_non_us"] * 100 for p in share_points] + [mid_de_pct_non_us * 100]
    colors = ['steelblue', 'darkorange', 'gray', 'purple', 'seagreen', 'crimson'][:len(values)]
    bars = ax.bar(labels, values, color=colors)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, v+0.4, f'{v:.1f}%', ha='center', fontsize=10, fontweight='bold')
    ax.axhline(y=mid_de_pct_non_us*100, color='crimson', linestyle='--', alpha=0.5, label=f'加权 {mid_de_pct_non_us*100:.1f}%')
    ax.set_ylabel('DE / 非美全球 (%)')
    ax.set_title('GL 旧品 DE / 非美 占比', fontsize=11, fontweight='bold')
    ax.legend(fontsize=10); ax.grid(True, alpha=0.3, axis='y')

    ax = axes[1, 0]
    ax.fill_between(months_idx, g_v2_p10, g_v2_p90,
                    alpha=0.15, color='darkorange', label='V2 multiplier P10~P90')
    ax.plot(months_idx, g_v1_mid, 'o-', color='steelblue', linewidth=2.2, markersize=6, label=f'V1 悲观 (Y1: {sum(g_v1_mid[:12]):,.0f})')
    ax.plot(months_idx, g_v2_mid, 's-', color='darkorange', linewidth=2.6, markersize=7, label=f'V2 中性 (Y1: {sum(g_v2_mid[:12]):,.0f})', zorder=5)
    ax.plot(months_idx, g_v3_mid, '^-', color='crimson', linewidth=2.2, markersize=6, label=f'V3 乐观 (Y1: {sum(g_v3_mid[:12]):,.0f})')
    ax.set_xticks(months_idx); ax.set_xticklabels(cal_short, rotation=45, fontsize=8)
    ax.set_xlabel('月份'); ax.set_ylabel('月销 (台)')
    ax.set_title(f'{CONFIG["forecast"].get("version", "unknown")} 全球非美 — V1/V2/V3 × {mult_mid:.2f}×', fontsize=11, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10); ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    cum_v1 = np.cumsum(g_v1_mid); cum_v2 = np.cumsum(g_v2_mid); cum_v3 = np.cumsum(g_v3_mid)
    ax.plot(months_idx, cum_v1, 'o-', color='steelblue', linewidth=2.2, markersize=5, label='V1 悲观')
    ax.plot(months_idx, cum_v2, 's-', color='darkorange', linewidth=2.6, markersize=6, label='V2 中性', zorder=5)
    ax.plot(months_idx, cum_v3, '^-', color='crimson', linewidth=2.2, markersize=5, label='V3 乐观')
    for series, color, label in [(cum_v1, 'steelblue', 'V1'), (cum_v2, 'darkorange', 'V2'), (cum_v3, 'crimson', 'V3')]:
        y1 = series[11]; m18 = series[17]
        ax.scatter([12, 18], [y1, m18], color=color, s=110, zorder=10, edgecolor='black', linewidth=1.2)
        ax.text(12.3, y1, f'{label} Y1 {y1:,.0f}', va='center', fontsize=8, color=color, fontweight='bold')
        ax.text(17.3, m18, f'{label} M18 {m18:,.0f}', va='center', fontsize=8, color=color, fontweight='bold')
    ax.set_xticks(months_idx); ax.set_xticklabels(cal_short, rotation=45, fontsize=8)
    ax.set_xlabel('月份'); ax.set_ylabel('累计销量 (台)')
    ax.set_title(f'{CONFIG["forecast"].get("version", "unknown")} 全球非美累计 — 三档', fontsize=11, fontweight='bold')
    ax.legend(loc='upper left', fontsize=10); ax.grid(True, alpha=0.3)

    plt.suptitle(f'{TARGET_PRODUCT.get("name", "Target Product")} 全球非美预测 {CONFIG["forecast"].get("version", "unknown")} — 基于 {de_source_label} DE × DE/非美占比反推',
                 fontsize=14, fontweight='bold', y=0.995)
    plt.tight_layout()
    out_png = output_paths["charts_png"]
    plt.savefig(out_png, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"写入 {out_png}")

    def fmt(v):
        try: return f"{v:,.0f}"
        except: return str(v)

    explanation_points = generate_explanation_points(
        anchor_scores,
        ANCHOR_PRODUCTS,
        product_results,
        TARGET_PRODUCT,
        manual_mid_de_pct_non_us,
        auto_mid_de_pct_non_us,
        mult_p10,
        mult_p50,
        mult_p90,
        mult_dist,
    )

    md = []
    md.append(f"# {TARGET_PRODUCT.get('name', 'Target Product')} {CONFIG['forecast'].get('scope', '全球除美国外')} 销量预测 {CONFIG['forecast'].get('version', 'unknown')}")
    md.append("")
    md.append(f"**生成日期**：{CONFIG['forecast'].get('generated_date', 'unknown')}")
    md.append(f"**版本**：{CONFIG['forecast'].get('version', 'unknown')}（基于 {de_source_label} DE × 反推系数）")
    md.append(f"**目标产品**：{TARGET_PRODUCT.get('name', 'unknown')}")
    md.append(f"**预测范围**：{CONFIG['forecast'].get('scope', '全球除美国外')}（{', '.join(TARGET_PRODUCT.get('target_regions') or REGIONS)}）")
    md.append(f"**锚点权重模式**：`{WEIGHT_MODE}`")
    md.append(f"**配置文件**：`{CONFIG_PATH}`")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 一、方法")
    md.append("")
    md.append(f"{de_source_label} 已给出 {TARGET_PRODUCT.get('name', '目标产品')} 在 **DE Amazon** 的月度三档预测。")
    md.append("本版基于 GL 旧品（BE9300 / MT6000）的 \"DE / 非美全球\" 实际销售占比反推。")
    md.append("")
    md.append("**公式**：")
    md.append("```")
    md.append(f"{TARGET_PRODUCT.get('name', '目标产品')}_全球非美(t) = {TARGET_PRODUCT.get('name', '目标产品')}_DE(t) × (1 / DE占非美比例)")
    md.append("```")
    md.append("")
    md.append("### 1.1 自动解释")
    md.append("")
    for point in explanation_points:
        md.append(f"- {point}")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 二、GL 旧品 DE / 非美 占比")
    md.append("")
    md.append("| 产品 | 时段 | 月数 | 美国 | 非美 | 德国 | DE / 非美 |")
    md.append("|---|---|---|---|---|---|---|")
    for product in ANCHOR_PRODUCTS:
        result = product_results[product["name"]]
        md.append(
            f"| {product.get('label', product['name'])} | {result['start_month']}~{result['end_month']} | "
            f"{result['n_months']} | {fmt(result['us'])} | {fmt(result['non_us'])} | "
            f"{fmt(result['de'])} | **{result['de_pct_non_us']*100:.1f}%** |"
        )
    md.append("")
    md.append(f"**加权综合**（{weight_text}）：**{mid_de_pct_non_us*100:.2f}%**")
    md.append("")
    md.append(f"- Manual 加权：DE/非美 **{manual_mid_de_pct_non_us*100:.2f}%**，multiplier **{manual_mult_mid:.2f}×**")
    md.append(f"- Auto 加权：DE/非美 **{auto_mid_de_pct_non_us*100:.2f}%**，multiplier **{auto_mult_mid:.2f}×**")
    md.append("")
    md.append("加权理由：当前权重由配置中的 `anchor_weighting.mode` 决定；auto 模式会综合锚点角色、产品参数相似度、数据新鲜度、样本窗口和数据质量。")
    md.append("")
    md.append("### 2.1 自动锚点评分")
    md.append("")
    md.append("| 锚点 | Manual 权重 | Auto 权重 | 总分 | role | product_fit | recency | window | data |")
    md.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for item in anchor_scores:
        parts = item["score_parts"]
        md.append(
            f"| {item['name']} | {item['manual_weight']:.2f} | **{item['auto_weight']:.2f}** | "
            f"{item['auto_score']:.3f} | {parts['role']:.2f} | {parts['product_fit']:.2f} | "
            f"{parts['recency']:.2f} | {parts['sample_window']:.2f} | {parts['data_quality']:.2f} |"
        )
    md.append("")
    md.append("### 2.2 product_fit 拆解")
    md.append("")
    md.append("| 锚点 | category | wifi_standard | band_type | price | positioning |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for item in anchor_scores:
        parts = item["product_fit_parts"]
        md.append(
            f"| {item['name']} | {parts['category']:.2f} | {parts['wifi_standard']:.2f} | {parts['band_type']:.2f} | "
            f"{parts['price']:.2f} | {parts['positioning']:.2f} |"
        )
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 三、反推系数")
    md.append("")
    md.append("### 3.1 原固定权重口径")
    md.append("")
    md.append("| 情景 | DE 占非美 | 反推系数 (DE × mult = 全球非美) |")
    md.append("|---|---|---|")
    md.append(f"| 保守 (low_mult) | {low_share_point['de_pct_non_us']*100:.1f}% ({low_share_point['label']}) | **{mult_low:.2f}×** |")
    md.append(f"| **中性 (mid_mult)** | **{mid_de_pct_non_us*100:.1f}%** (加权) | **{mult_mid:.2f}×** |")
    md.append(f"| 乐观 (high_mult) | {high_share_point['de_pct_non_us']*100:.1f}% ({high_share_point['label']}) | **{mult_high:.2f}×** |")
    md.append("")
    md.append("### 3.2 新增 Monte Carlo 分布口径")
    md.append("")
    md.append(f"- 抽样次数：{N_MONTE_CARLO:,}")
    md.append(f"- 随机种子：{RANDOM_SEED}")
    md.append("- 方法：对历史 DE/非美占比做加权 logit-normal 抽样，再转换为 `multiplier = 1 / DE_share`。")
    md.append("")
    md.append("| 销量口径 | P10（保守销量） | P50（中性销量） | P90（偏高销量） |")
    md.append("|---|---:|---:|---:|")
    md.append(f"| 对应 DE / 非美占比 | {mult_dist['share_p90']*100:.1f}% | {mult_dist['share_p50']*100:.1f}% | {mult_dist['share_p10']*100:.1f}% |")
    md.append(f"| 对应反推系数 multiplier | **{mult_p10:.2f}×** | **{mult_p50:.2f}×** | **{mult_p90:.2f}×** |")
    md.append("")
    md.append("> 注：DE 占比和 multiplier 方向相反；销量口径 P10 对应较高 DE 占比和较低 multiplier，销量口径 P90 对应较低 DE 占比和较高 multiplier。")
    md.append("")
    md.append("---")
    md.append("")
    md.append(f"## 四、{TARGET_PRODUCT.get('name', '目标产品')} 全球非美 月销预测（V2 中性 × multiplier 分布）")
    md.append("")
    md.append(f"| M | 月份 | DE {de_source_label} | 全球非美 P10 | 全球非美 P50 | 全球非美 P90 | 固定中性 | 备注 |")
    md.append("|---|---|---:|---:|---:|---:|---:|---|")
    for i, r in enumerate(de_forecast):
        note = ""
        if r['M'] == 1: note = "M1 上市"
        elif r['M'] == 5: note = "BF Y1"
        elif r['M'] == 13: note = "PD Y2 ★ 峰值"
        elif r['M'] == 17: note = "BF Y2"
        md.append(f"| M{r['M']} | {r['cal']} | {fmt(r['v2_mid'])} | {fmt(g_v2_p10[i])} | **{fmt(g_v2_p50[i])}** | {fmt(g_v2_p90[i])} | {fmt(g_v2_mid[i])} | {note} |")
    y1_de = sum(r['v2_mid'] for r in de_forecast[:12])
    m18_de = sum(r['v2_mid'] for r in de_forecast)
    md.append(f"| **Y1** | M1-M12 | **{fmt(y1_de)}** | **{fmt(sum(g_v2_p10[:12]))}** | **{fmt(sum(g_v2_p50[:12]))}** | **{fmt(sum(g_v2_p90[:12]))}** | **{fmt(sum(g_v2_mid[:12]))}** | |")
    md.append(f"| **M18** | M1-M18 | **{fmt(m18_de)}** | **{fmt(sum(g_v2_p10))}** | **{fmt(sum(g_v2_p50))}** | **{fmt(sum(g_v2_p90))}** | **{fmt(sum(g_v2_mid))}** | |")
    md.append("")
    md.append("---")
    md.append("")
    md.append(f"## 五、{TARGET_PRODUCT.get('name', '目标产品')} 全球非美 三档（V1/V2/V3，中性 mult）")
    md.append("")
    md.append(f"| 档位 | DE Y1 ({de_source_label}) | 全球非美 Y1 | DE M18 | 全球非美 M18 |")
    md.append("|---|---|---|---|---|")
    y1_v1_de = sum(r['v1_mid'] for r in de_forecast[:12])
    y1_v3_de = sum(r['v3_mid'] for r in de_forecast[:12])
    m18_v1_de = sum(r['v1_mid'] for r in de_forecast)
    m18_v3_de = sum(r['v3_mid'] for r in de_forecast)
    md.append(f"| V1 悲观 | {fmt(y1_v1_de)} | **{fmt(sum(g_v1_mid[:12]))}** | {fmt(m18_v1_de)} | **{fmt(sum(g_v1_mid))}** |")
    md.append(f"| **V2 中性** | **{fmt(y1_de)}** | **{fmt(sum(g_v2_mid[:12]))}** | **{fmt(m18_de)}** | **{fmt(sum(g_v2_mid))}** |")
    md.append(f"| V3 乐观 | {fmt(y1_v3_de)} | **{fmt(sum(g_v3_mid[:12]))}** | {fmt(m18_v3_de)} | **{fmt(sum(g_v3_mid))}** |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 六、关键数字（V2 中性，全球非美）")
    md.append("")
    md.append("| 节点 | DE | 全球非美 | 倍数 |")
    md.append("|---|---|---|---|")
    md.append(f"| M1 (上市) | {fmt(de_forecast[0]['v2_mid'])} | **{fmt(g_v2_mid[0])}** | {mult_mid:.2f}× |")
    md.append(f"| M5 (BF Y1) | {fmt(de_forecast[4]['v2_mid'])} | **{fmt(g_v2_mid[4])}** | {mult_mid:.2f}× |")
    md.append(f"| M13 (PD Y2) ⭐ | {fmt(de_forecast[12]['v2_mid'])} | **{fmt(g_v2_mid[12])}** | {mult_mid:.2f}× |")
    md.append(f"| M17 (BF Y2) | {fmt(de_forecast[16]['v2_mid'])} | **{fmt(g_v2_mid[16])}** | {mult_mid:.2f}× |")
    md.append(f"| **Y1 总量（固定中性）** | **{fmt(y1_de)}** | **{fmt(sum(g_v2_mid[:12]))}** | {mult_mid:.2f}× |")
    md.append(f"| **Y1 总量（分布 P50）** | **{fmt(y1_de)}** | **{fmt(sum(g_v2_p50[:12]))}** | {mult_p50:.2f}× |")
    md.append(f"| **M18 总量（固定中性）** | **{fmt(m18_de)}** | **{fmt(sum(g_v2_mid))}** | {mult_mid:.2f}× |")
    md.append(f"| **M18 总量（分布 P50）** | **{fmt(m18_de)}** | **{fmt(sum(g_v2_p50))}** | {mult_p50:.2f}× |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 七、注意事项")
    md.append("")
    md.append(f"1. **占比基于历史规律**：{TARGET_PRODUCT.get('name', '目标产品')} 实际地区分布可能因营销策略 / 区域定价不同而偏差")
    md.append(f"2. **不含美国**：当前输出为全球非美口径，DE 输入来源为 {de_source_label}")
    md.append(f"3. **加权选择**：当前权重模式为 `{WEIGHT_MODE}`，报告已展示 Manual 与 Auto 权重")
    md.append("4. **分布区间**：P10/P50/P90 只反映 DE/非美占比不确定性，尚未叠加 DE 本身预测误差")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 数据声明")
    md.append("- GL.iNet 内部参考性销量预估")
    md.append("- 含商业敏感数据，仅限内部传阅")
    md.append("")
    md.append(f"*生成日期：{CONFIG['forecast'].get('generated_date', 'unknown')} | 模型版本：{CONFIG['forecast'].get('version', 'unknown')}*")
    output_paths["method_md"].write_text("\n".join(md))
    print(f"写入 {output_paths['method_md']}")

    summary = []
    peak_idx = int(np.argmax(g_v2_p50))
    peak_row = de_forecast[peak_idx]
    bf_y1_idx = 4
    pd_y2_idx = 12
    bf_y2_idx = 16

    summary.append(f"# {TARGET_PRODUCT.get('name', 'Target Product')} 全球非美销量预测摘要")
    summary.append("")
    summary.append(f"**生成日期**：{CONFIG['forecast'].get('generated_date', 'unknown')}")
    summary.append(f"**模型版本**：{CONFIG['forecast'].get('version', 'unknown')}")
    summary.append(f"**权重模式**：`{WEIGHT_MODE}`")
    summary.append(f"**预测范围**：{CONFIG['forecast'].get('scope', '全球除美国外')}（{', '.join(TARGET_PRODUCT.get('target_regions') or REGIONS)}）")
    summary.append("")
    summary.append("## 1. 结论")
    summary.append("")
    summary.append(f"- 经营计划线建议看 **P50**：Y1 **{fmt(sum(g_v2_p50[:12]))}** 台，M18 **{fmt(sum(g_v2_p50))}** 台。")
    summary.append(f"- 保守备货线建议看 **P10**：Y1 **{fmt(sum(g_v2_p10[:12]))}** 台，M18 **{fmt(sum(g_v2_p10))}** 台。")
    summary.append(f"- 产能风险线建议看 **P90**：Y1 **{fmt(sum(g_v2_p90[:12]))}** 台，M18 **{fmt(sum(g_v2_p90))}** 台。")
    summary.append(f"- P50 峰值月为 **M{peak_row['M']} ({peak_row['cal']})**，全球非美月销约 **{fmt(g_v2_p50[peak_idx])}** 台。")
    summary.append("")
    summary.append("## 2. 自动解释")
    summary.append("")
    for point in explanation_points:
        summary.append(f"- {point}")
    summary.append("")
    summary.append("## 3. 核心数字")
    summary.append("")
    summary.append("| 指标 | DE V2 | 全球非美 P10 | 全球非美 P50 | 全球非美 P90 | 固定中性 |")
    summary.append("|---|---:|---:|---:|---:|---:|")
    summary.append(f"| Y1 累计 | {fmt(y1_de)} | **{fmt(sum(g_v2_p10[:12]))}** | **{fmt(sum(g_v2_p50[:12]))}** | **{fmt(sum(g_v2_p90[:12]))}** | {fmt(sum(g_v2_mid[:12]))} |")
    summary.append(f"| M18 累计 | {fmt(m18_de)} | **{fmt(sum(g_v2_p10))}** | **{fmt(sum(g_v2_p50))}** | **{fmt(sum(g_v2_p90))}** | {fmt(sum(g_v2_mid))} |")
    summary.append(f"| 峰值月 | M{peak_row['M']} | {fmt(g_v2_p10[peak_idx])} | **{fmt(g_v2_p50[peak_idx])}** | {fmt(g_v2_p90[peak_idx])} | {fmt(g_v2_mid[peak_idx])} |")
    summary.append("")
    summary.append("## 4. 关键月份")
    summary.append("")
    summary.append("| 节点 | 月份 | DE V2 | 全球非美 P10 | 全球非美 P50 | 全球非美 P90 |")
    summary.append("|---|---|---:|---:|---:|---:|")
    for label, idx in [("M1 上市", 0), ("BF Y1", bf_y1_idx), ("PD Y2", pd_y2_idx), ("BF Y2", bf_y2_idx)]:
        r = de_forecast[idx]
        summary.append(f"| {label} | {r['cal']} | {fmt(r['v2_mid'])} | {fmt(g_v2_p10[idx])} | **{fmt(g_v2_p50[idx])}** | {fmt(g_v2_p90[idx])} |")
    summary.append("")
    summary.append("## 5. 锚点权重")
    summary.append("")
    summary.append("| 锚点 | Manual 权重 | Auto 权重 | product_fit | DE/非美 |")
    summary.append("|---|---:|---:|---:|---:|")
    for item in anchor_scores:
        result = product_results[item["name"]]
        summary.append(
            f"| {item['name']} | {item['manual_weight']:.2f} | **{item['auto_weight']:.2f}** | "
            f"{item['score_parts']['product_fit']:.2f} | {result['de_pct_non_us']*100:.1f}% |"
        )
    summary.append("")
    summary.append("## 6. Multiplier")
    summary.append("")
    summary.append("| 销量口径 | 对应 DE/非美 | 对应 multiplier |")
    summary.append("|---|---:|---:|")
    summary.append(f"| Manual 加权 | {manual_mid_de_pct_non_us*100:.2f}% | {manual_mult_mid:.2f}x |")
    summary.append(f"| Auto 加权 | {auto_mid_de_pct_non_us*100:.2f}% | {auto_mult_mid:.2f}x |")
    summary.append(f"| Monte Carlo P10 | {mult_dist['share_p90']*100:.1f}% | {mult_p10:.2f}x |")
    summary.append(f"| Monte Carlo P50 | {mult_dist['share_p50']*100:.1f}% | {mult_p50:.2f}x |")
    summary.append(f"| Monte Carlo P90 | {mult_dist['share_p10']*100:.1f}% | {mult_p90:.2f}x |")
    summary.append("")
    summary.append("> DE 占比和 multiplier 方向相反；这里按销量口径排列。")
    summary.append("")
    summary.append("## 7. 使用口径")
    summary.append("")
    summary.append("- **P10**：偏保守，用于首批备货和现金风险控制。")
    summary.append("- **P50**：中性经营线，用于业务计划和跨部门沟通。")
    summary.append("- **P90**：偏高需求线，用于产能、库存上限和断货风险评估。")
    summary.append("- 当前区间只反映 DE/非美占比和 multiplier 不确定性，尚未叠加 DE 预测本身误差。")
    summary.append("- 当前预测不含美国市场。")
    summary.append("")
    summary.append("## 8. 输出文件")
    summary.append("")
    summary.append(f"- CSV：`{output_paths['csv']}`")
    summary.append(f"- 图表：`{output_paths['charts_png']}`")
    summary.append(f"- 方法说明：`{output_paths['method_md']}`")
    summary.append(f"- 配置文件：`{CONFIG_PATH}`")
    summary.append("")
    summary.append("---")
    summary.append("")
    summary.append("数据声明：GL.iNet 内部参考性销量预估，仅限内部传阅。")

    summary_path = output_paths["summary_md"]
    summary_path.write_text("\n".join(summary))
    print(f"写入 {summary_path}")

    timeline_events = []
    event_tooltips = {}
    for event in TIMELINE_EVENTS:
        m = int(event.get("m", 0))
        idx = m - 1
        in_range = 0 <= idx < len(de_forecast)
        row = de_forecast[idx] if in_range else None
        item = {
            "m": m,
            "index": idx,
            "month": row["cal"] if row else f"M{m}+",
            "type": event.get("type", "milestone"),
            "label": event.get("label", f"M{m}"),
            "detail": event.get("detail", ""),
            "inRange": in_range,
            "y": round(g_v2_p90[idx] * 1.04) if in_range else None,
        }
        timeline_events.append(item)
        if in_range:
            event_tooltips.setdefault(idx, []).append(item)

    html_data = {
        "months": [r["cal"] for r in de_forecast],
        "monthLabels": [f"M{r['M']}" for r in de_forecast],
        "deV2": [round(r["v2_mid"]) for r in de_forecast],
        "p10": [round(v) for v in g_v2_p10],
        "p50": [round(v) for v in g_v2_p50],
        "p90": [round(v) for v in g_v2_p90],
        "fixedMid": [round(v) for v in g_v2_mid],
        "cumP10": [round(v) for v in np.cumsum(g_v2_p10)],
        "cumP50": [round(v) for v in np.cumsum(g_v2_p50)],
        "cumP90": [round(v) for v in np.cumsum(g_v2_p90)],
        "cumFixedMid": [round(v) for v in np.cumsum(g_v2_mid)],
        "events": {idx: "<br/>".join(f"{e['label']}：{e['detail']}" for e in events) for idx, events in event_tooltips.items()},
        "timelineEvents": timeline_events,
        "anchorWeights": [
            {
                "name": item["name"],
                "manual": round(item["manual_weight"], 4),
                "auto": round(item["auto_weight"], 4),
                "productFit": round(item["score_parts"]["product_fit"], 4),
                "deShare": round(product_results[item["name"]]["de_pct_non_us"] * 100, 2),
            }
            for item in anchor_scores
        ],
        "productFitParts": [
            {
                "name": item["name"],
                "category": round(item["product_fit_parts"]["category"], 4),
                "wifi": round(item["product_fit_parts"]["wifi_standard"], 4),
                "band": round(item["product_fit_parts"]["band_type"], 4),
                "price": round(item["product_fit_parts"]["price"], 4),
                "positioning": round(item["product_fit_parts"]["positioning"], 4),
            }
            for item in anchor_scores
        ],
    }

    html = """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITLE__</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Noto+Sans+SC:wght@300;400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
    :root {
      --teal-deep:#274753; --teal:#297270; --teal-mid:#299d8f; --sage:#8ab07c;
      --gold:#e7c66b; --orange:#f3a361; --coral:#e66d50;
      --blue:#297270; --blue-light:#d4eeeb; --emerald:#299d8f; --emerald-bg:#dff0ed;
      --amber:#f3a361; --amber-bg:#fef0e0; --red:#e66d50; --red-bg:#fce8e3;
      --slate:#274753; --slate-2:#2f5a5e; --muted:#5e8a87; --muted-2:#8db5b0;
      --border:#d8e5e2; --border-2:#b8cdc8; --bg:#f4f7f5; --card:#fff;
      --radius:14px; --radius-sm:8px;
      --shadow-sm:0 1px 3px rgba(39,71,83,.06),0 1px 2px rgba(39,71,83,.04);
      --shadow:0 4px 16px rgba(39,71,83,.08),0 1px 4px rgba(39,71,83,.04);
      --shadow-lg:0 12px 40px rgba(39,71,83,.12);
    }
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Plus Jakarta Sans','Noto Sans SC','PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;background:var(--bg);color:var(--slate);line-height:1.65;-webkit-font-smoothing:antialiased}
    .container{max-width:1160px;margin:0 auto;padding:28px 20px 48px}
    .report-header{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);margin-bottom:24px;overflow:hidden;display:grid;grid-template-columns:6px 1fr}
    .header-accent{background:linear-gradient(180deg,var(--teal-deep),var(--teal))}
    .header-body{padding:40px 44px 36px}
    .header-badge{display:inline-block;background:var(--blue-light);color:var(--blue);font-size:10px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase;padding:3px 10px;border-radius:20px;margin-bottom:14px}
    h1{font-size:28px;font-weight:800;line-height:1.25;letter-spacing:-.5px;margin-bottom:24px}
    .header-meta{display:grid;grid-template-columns:repeat(4,auto);width:fit-content;border:1px solid var(--border);border-radius:var(--radius-sm);overflow:hidden}
    .meta-cell{padding:10px 20px;border-right:1px solid var(--border)}.meta-cell:last-child{border-right:none}
    .meta-label{font-size:10px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:var(--muted-2);margin-bottom:3px}.meta-value{font-size:13px;font-weight:600;color:var(--slate-2)}
    .section{background:var(--card);border-radius:var(--radius);box-shadow:var(--shadow);padding:36px 40px;margin-bottom:20px;border-top:3px solid var(--teal)}
    .section:nth-of-type(2){border-top-color:var(--teal-mid)}.section:nth-of-type(3){border-top-color:var(--sage)}.section:nth-of-type(4){border-top-color:var(--gold)}
    .section-label{display:inline-flex;align-items:center;gap:6px;font-size:10px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:2px;margin-bottom:6px}
    .section-label:before{content:'';width:12px;height:2px;background:currentColor;border-radius:2px}
    h2{font-size:22px;font-weight:800;letter-spacing:-.4px;margin-bottom:8px;line-height:1.25}.desc{font-size:14px;color:var(--muted);margin-bottom:24px;max-width:820px}
    .ad-kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:20px 0 24px}
    .ad-kpi-card{border-radius:var(--radius-sm);padding:22px 18px 18px;text-align:center;border:1.5px solid var(--border);background:var(--card);transition:box-shadow .2s,transform .2s}
    .ad-kpi-card:hover{transform:translateY(-2px);box-shadow:var(--shadow-lg)}.ad-kpi-card.highlight{background:linear-gradient(160deg,#eaf5f0,#dff0ed);border-color:var(--teal-mid)}
    .ad-kpi-label{font-size:10px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted);margin-bottom:10px}.ad-kpi-value{font-size:28px;font-weight:800;line-height:1;letter-spacing:-1px;color:var(--slate);margin-bottom:4px}.ad-kpi-value .unit{font-size:16px}.ad-kpi-sub{font-size:11px;color:var(--muted-2);margin-top:6px}
    .chart-box{width:100%;height:420px;border:1px solid var(--border);border-radius:var(--radius-sm);background:#fff;margin-top:16px}.chart-box.small{height:330px}
    .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:16px}.insight{margin-top:18px;padding:16px 18px;border-radius:var(--radius-sm);background:#eaf5f0;border-left:4px solid var(--teal-mid);font-size:13px;color:var(--slate-2)}.insight.warning{background:#fef8f0;border-left-color:var(--orange)}
    .explain-list{margin-top:16px;padding-left:18px;font-size:13px;color:var(--slate-2)}.explain-list li{margin-bottom:8px}
    table{width:100%;border-collapse:collapse;font-size:13px;margin-top:16px}th{background:#eef5f2;color:var(--slate);font-size:11px;text-transform:uppercase;letter-spacing:.7px;text-align:left;padding:10px 12px}td{border-bottom:1px solid var(--border);padding:11px 12px}td.num,th.num{text-align:right}.good{color:var(--teal-mid);font-weight:700}.warn{color:var(--orange);font-weight:700}.bad{color:var(--coral);font-weight:700}
    .tag{display:inline-block;border-radius:20px;padding:2px 9px;font-size:10px;font-weight:800;letter-spacing:.8px;text-transform:uppercase}
    .tag.promotion{background:var(--amber-bg);color:#7a4a1a}.tag.calibration{background:var(--blue-light);color:var(--teal)}.tag.launch{background:var(--emerald-bg);color:var(--teal-deep)}.tag.model_switch{background:var(--red-bg);color:var(--coral)}
    .report-footer{text-align:center;color:var(--muted-2);font-size:11px;margin-top:24px}
    @media(max-width:820px){.header-body{padding:28px 24px}.header-meta{grid-template-columns:1fr 1fr;width:100%}.ad-kpi-grid,.grid-2{grid-template-columns:1fr}.section{padding:28px 22px}.chart-box{height:360px}}
    </style>
    </head>
    <body>
    <div class="container">
      <header class="report-header">
        <div class="header-accent"></div>
        <div class="header-body">
          <div class="header-badge">Forecast Tool Output</div>
          <h1>__TITLE__</h1>
          <div class="header-meta">
            <div class="meta-cell"><div class="meta-label">Product</div><div class="meta-value">__PRODUCT__</div></div>
            <div class="meta-cell"><div class="meta-label">Version</div><div class="meta-value">__VERSION__</div></div>
            <div class="meta-cell"><div class="meta-label">Weight Mode</div><div class="meta-value">__WEIGHT_MODE__</div></div>
            <div class="meta-cell"><div class="meta-label">Scope</div><div class="meta-value">Global ex-US</div></div>
          </div>
        </div>
      </header>

      <section class="section">
        <div class="section-label">Executive View</div>
        <h2>P10 / P50 / P90 经营口径</h2>
        <p class="desc">P10 用于保守备货，P50 用于经营计划，P90 用于产能和断货风险评估。当前区间只反映 DE/非美 multiplier 不确定性。</p>
        <div class="ad-kpi-grid">
          <div class="ad-kpi-card"><div class="ad-kpi-label">Y1 P10</div><div class="ad-kpi-value">__Y1_P10__<span class="unit">台</span></div><div class="ad-kpi-sub">保守备货线</div></div>
          <div class="ad-kpi-card highlight"><div class="ad-kpi-label">Y1 P50</div><div class="ad-kpi-value">__Y1_P50__<span class="unit">台</span></div><div class="ad-kpi-sub">经营计划线</div></div>
          <div class="ad-kpi-card"><div class="ad-kpi-label">Y1 P90</div><div class="ad-kpi-value">__Y1_P90__<span class="unit">台</span></div><div class="ad-kpi-sub">产能风险线</div></div>
          <div class="ad-kpi-card"><div class="ad-kpi-label">Peak Month</div><div class="ad-kpi-value">M__PEAK_M__</div><div class="ad-kpi-sub">__PEAK_CAL__ · P50 __PEAK_VALUE__ 台</div></div>
        </div>
        <div id="monthlyChart" class="chart-box"></div>
        <div class="insight">曲线支持 hover：可查看每月 DE V2、全球非美 P10/P50/P90、固定中性，以及促销活动、模型校准和模型切换节点。</div>
        <div id="cumulativeChart" class="chart-box"></div>
        <div class="insight">累计图用于判断全年备货和 18 个月产能压力；Y1 与 M18 关键点已在图上标注。</div>
      </section>

      <section class="section">
        <div class="section-label">Auto Explanation</div>
        <h2>预测解释</h2>
        <p class="desc">以下说明由锚点权重、产品相似度、DE/非美占比和 multiplier 分布自动生成，用于帮助汇报时解释数字来源。</p>
        <ul class="explain-list">__EXPLANATION_ITEMS__</ul>
      </section>

      <section class="section">
        <div class="section-label">Anchor Logic</div>
        <h2>锚点权重与产品相似度</h2>
        <p class="desc">Auto 权重综合 role、product_fit、recency、sample window 和 data quality。product_fit 由品类、Wi-Fi 标准、频段、价格和定位构成。</p>
        <div class="grid-2">
          <div><div id="weightChart" class="chart-box small"></div></div>
          <div><div id="fitChart" class="chart-box small"></div></div>
        </div>
        <table>
          <thead><tr><th>锚点</th><th class="num">Manual</th><th class="num">Auto</th><th class="num">Product Fit</th><th class="num">DE/非美</th></tr></thead>
          <tbody>__ANCHOR_ROWS__</tbody>
        </table>
      </section>

      <section class="section">
        <div class="section-label">Multiplier</div>
        <h2>DE / 非美占比与反推系数</h2>
        <p class="desc">DE 占比越低，全球非美 multiplier 越高。Monte Carlo 输出比固定三档更适合作为风险区间。</p>
        <div class="ad-kpi-grid">
          <div class="ad-kpi-card"><div class="ad-kpi-label">Manual Mult</div><div class="ad-kpi-value">__MANUAL_MULT__<span class="unit">x</span></div><div class="ad-kpi-sub">原人工权重</div></div>
          <div class="ad-kpi-card highlight"><div class="ad-kpi-label">Auto Mult</div><div class="ad-kpi-value">__AUTO_MULT__<span class="unit">x</span></div><div class="ad-kpi-sub">当前固定中性</div></div>
          <div class="ad-kpi-card"><div class="ad-kpi-label">MC P50</div><div class="ad-kpi-value">__MC_P50__<span class="unit">x</span></div><div class="ad-kpi-sub">分布中位数</div></div>
          <div class="ad-kpi-card"><div class="ad-kpi-label">MC P90</div><div class="ad-kpi-value">__MC_P90__<span class="unit">x</span></div><div class="ad-kpi-sub">偏高需求线</div></div>
        </div>
        <div id="multChart" class="chart-box small"></div>
      </section>

      <section class="section">
        <div class="section-label">Key Months</div>
        <h2>关键月份明细</h2>
        <table>
          <thead><tr><th>节点</th><th>月份</th><th class="num">DE V2</th><th class="num">P10</th><th class="num">P50</th><th class="num">P90</th></tr></thead>
          <tbody>__KEY_ROWS__</tbody>
        </table>
        <h2 style="margin-top:28px;font-size:17px;">促销活动与模型校准时间线</h2>
        <table>
          <thead><tr><th>类型</th><th>节点</th><th>月份</th><th>说明</th></tr></thead>
          <tbody>__TIMELINE_ROWS__</tbody>
        </table>
        <div class="insight warning">当前 HTML 是交互式结果展示，不替代 CSV。正式计算口径仍以同目录 CSV 和 method markdown 为准。</div>
      </section>

      <footer class="report-footer">GL.iNet Data Team · Internal reference only · __GENERATED_DATE__</footer>
    </div>

    <script>
    const DATA = __DATA_JSON__;
    const C = { tealDeep:'#274753', teal:'#297270', tealMid:'#299d8f', sage:'#8ab07c', gold:'#e7c66b', orange:'#f3a361', coral:'#e66d50', border:'#d8e5e2', muted:'#5e8a87' };
    function fmt(n){ return Number(n).toLocaleString('en-US'); }
    function tooltipStyle(){ return { backgroundColor:'rgba(255,255,255,.96)', borderColor:C.border, borderWidth:1, textStyle:{color:C.tealDeep}, extraCssText:'box-shadow:0 8px 24px rgba(39,71,83,.12);border-radius:8px;' }; }
    function axisStyle(){ return { axisLine:{lineStyle:{color:C.border}}, axisTick:{show:false}, axisLabel:{color:C.muted}, splitLine:{lineStyle:{color:'#edf3f1'}} }; }
    function initChart(id){ const el=document.getElementById(id); const chart=echarts.init(el); window.addEventListener('resize',()=>chart.resize()); return chart; }

    const monthly = initChart('monthlyChart');
    const xCats = DATA.monthLabels.map((m,i)=>`${m}\n${DATA.months[i].slice(2)}`);
    const promoEvents = DATA.timelineEvents.filter(e=>e.inRange && ['launch','promotion'].includes(e.type));
    const calibrationEvents = DATA.timelineEvents.filter(e=>e.inRange && ['calibration','model_switch'].includes(e.type));
    monthly.setOption({
      color:[C.sage,C.tealMid,C.orange,C.tealDeep,C.coral,C.gold,C.teal],
      tooltip:{...tooltipStyle(), trigger:'axis', formatter:(params)=>{
        const i=params[0].dataIndex; const event=DATA.events[i] ? `<br/><b>${DATA.events[i]}</b>` : '';
        return `<b>${DATA.monthLabels[i]} · ${DATA.months[i]}</b>${event}<br/>` + params.map(p=>{
          const value = Array.isArray(p.value) ? p.value[1] : p.value;
          return `${p.marker}${p.seriesName}: <b>${fmt(value)}</b>`;
        }).join('<br/>');
      }},
      legend:{top:8},
      grid:{left:52,right:24,top:58,bottom:42},
      xAxis:{type:'category', data:xCats, ...axisStyle()},
      yAxis:{type:'value', ...axisStyle(), axisLabel:{color:C.muted, formatter:(v)=>fmt(v)}},
      series:[
        {name:'P10', type:'line', smooth:true, data:DATA.p10, symbolSize:6, lineStyle:{width:2},
          markLine:{symbol:'none', silent:false, label:{formatter:(p)=>p.name, color:C.teal, fontWeight:800, fontSize:10},
            lineStyle:{color:C.teal, type:'dashed', width:1.5, opacity:.72},
            data:calibrationEvents.map(e=>({name:e.label, xAxis:xCats[e.index]}))}},
        {name:'P50', type:'line', smooth:true, data:DATA.p50, symbolSize:7, lineStyle:{width:4}},
        {name:'P90', type:'line', smooth:true, data:DATA.p90, symbolSize:6, lineStyle:{width:2}},
        {name:'固定中性', type:'line', smooth:true, data:DATA.fixedMid, symbol:'none', lineStyle:{width:2,type:'dashed'}},
        {name:'DE V2', type:'bar', data:DATA.deV2, barWidth:14, yAxisIndex:0, itemStyle:{opacity:.28}},
        {name:'促销/上市', type:'scatter', symbol:'pin', symbolSize:46,
          data:promoEvents.map(e=>({name:e.label, value:[xCats[e.index], e.y], detail:e.detail})),
          itemStyle:{color:C.orange}, label:{show:true, formatter:(p)=>p.name, position:'top', color:C.orange, fontWeight:800, fontSize:10}},
      ],
      dataZoom:[{type:'inside'}, {type:'slider', height:18, bottom:8}]
    });

    const cumulative = initChart('cumulativeChart');
    cumulative.setOption({
      color:[C.sage,C.tealMid,C.orange,C.tealDeep],
      tooltip:{...tooltipStyle(), trigger:'axis', formatter:(params)=>{
        const i=params[0].dataIndex;
        return `<b>${DATA.monthLabels[i]} · ${DATA.months[i]}</b><br/>` + params.map(p=>`${p.marker}${p.seriesName}: <b>${fmt(p.value)}</b>`).join('<br/>');
      }},
      legend:{top:8},
      grid:{left:62,right:28,top:58,bottom:42},
      xAxis:{type:'category', data:xCats, ...axisStyle()},
      yAxis:{type:'value', ...axisStyle(), axisLabel:{color:C.muted, formatter:(v)=>fmt(v)}},
      series:[
        {name:'累计 P10', type:'line', smooth:true, data:DATA.cumP10, symbolSize:5, lineStyle:{width:2}},
        {name:'累计 P50', type:'line', smooth:true, data:DATA.cumP50, symbolSize:6, lineStyle:{width:4},
          markPoint:{symbol:'pin', symbolSize:58, itemStyle:{color:C.tealMid}, label:{formatter:(p)=>p.name},
            data:[
              {name:'Y1', coord:[xCats[11], DATA.cumP50[11]], value:DATA.cumP50[11]},
              {name:'M18', coord:[xCats[17], DATA.cumP50[17]], value:DATA.cumP50[17]},
            ]}},
        {name:'累计 P90', type:'line', smooth:true, data:DATA.cumP90, symbolSize:5, lineStyle:{width:2}},
        {name:'累计固定中性', type:'line', smooth:true, data:DATA.cumFixedMid, symbol:'none', lineStyle:{width:2,type:'dashed'}},
      ],
      dataZoom:[{type:'inside'}, {type:'slider', height:18, bottom:8}]
    });

    const weightChart = initChart('weightChart');
    weightChart.setOption({
      color:[C.teal,C.orange],
      tooltip:{...tooltipStyle(), trigger:'axis', axisPointer:{type:'shadow'}, formatter:(p)=>`<b>${p[0].name}</b><br/>${p.map(x=>`${x.marker}${x.seriesName}: <b>${(x.value*100).toFixed(1)}%</b>`).join('<br/>')}`},
      legend:{top:4},
      grid:{left:50,right:18,top:48,bottom:42},
      xAxis:{type:'category', data:DATA.anchorWeights.map(x=>x.name), ...axisStyle()},
      yAxis:{type:'value', max:0.6, ...axisStyle(), axisLabel:{color:C.muted, formatter:(v)=>(v*100).toFixed(0)+'%'}},
      series:[
        {name:'Manual', type:'bar', data:DATA.anchorWeights.map(x=>x.manual), barWidth:18},
        {name:'Auto', type:'bar', data:DATA.anchorWeights.map(x=>x.auto), barWidth:18},
      ]
    });

    const fitChart = initChart('fitChart');
    fitChart.setOption({
      color:[C.tealDeep,C.tealMid,C.sage,C.gold,C.coral],
      tooltip:{...tooltipStyle(), trigger:'axis', axisPointer:{type:'shadow'}},
      legend:{top:4},
      grid:{left:50,right:18,top:48,bottom:42},
      xAxis:{type:'category', data:DATA.productFitParts.map(x=>x.name), ...axisStyle()},
      yAxis:{type:'value', max:1, ...axisStyle(), axisLabel:{color:C.muted, formatter:(v)=>(v*100).toFixed(0)}},
      series:[
    {name:'Category', type:'bar', data:DATA.productFitParts.map(x=>x.category)},
    {name:'Wi-Fi', type:'bar', data:DATA.productFitParts.map(x=>x.wifi)},
    {name:'Band', type:'bar', data:DATA.productFitParts.map(x=>x.band)},
    {name:'Price', type:'bar', data:DATA.productFitParts.map(x=>x.price)},
    {name:'Positioning', type:'bar', data:DATA.productFitParts.map(x=>x.positioning)},
      ]
    });

    const multChart = initChart('multChart');
    multChart.setOption({
      color:[C.sage,C.tealMid,C.orange],
      tooltip:{...tooltipStyle(), trigger:'axis'},
      grid:{left:52,right:24,top:24,bottom:36},
      xAxis:{type:'category', data:['P10','P50','P90'], ...axisStyle()},
      yAxis:{type:'value', ...axisStyle(), axisLabel:{color:C.muted, formatter:(v)=>v.toFixed(1)+'x'}},
      series:[{name:'Multiplier', type:'bar', barWidth:42, data:[__MC_P10_NUM__,__MC_P50_NUM__,__MC_P90_NUM__],
        label:{show:true, position:'top', formatter:(p)=>p.value.toFixed(2)+'x'}}]
    });
    </script>
    </body>
    </html>
    """

    anchor_rows = []
    for item in anchor_scores:
        result = product_results[item["name"]]
        anchor_rows.append(
            f"<tr><td>{item['name']}</td><td class='num'>{item['manual_weight']:.2f}</td>"
            f"<td class='num good'>{item['auto_weight']:.2f}</td><td class='num'>{item['score_parts']['product_fit']:.2f}</td>"
            f"<td class='num'>{result['de_pct_non_us']*100:.1f}%</td></tr>"
        )
    key_rows = []
    for label, idx in [("M1 上市", 0), ("BF Y1", bf_y1_idx), ("PD Y2", pd_y2_idx), ("BF Y2", bf_y2_idx)]:
        r = de_forecast[idx]
        key_rows.append(
            f"<tr><td>{label}</td><td>{r['cal']}</td><td class='num'>{fmt(r['v2_mid'])}</td>"
            f"<td class='num'>{fmt(g_v2_p10[idx])}</td><td class='num good'>{fmt(g_v2_p50[idx])}</td>"
            f"<td class='num warn'>{fmt(g_v2_p90[idx])}</td></tr>"
        )
    timeline_type_labels = {
        "launch": "上市",
        "promotion": "促销",
        "calibration": "校准",
        "model_switch": "切换",
    }
    timeline_rows = []
    for event in timeline_events:
        event_type = event["type"]
        timeline_rows.append(
            f"<tr><td><span class='tag {event_type}'>{timeline_type_labels.get(event_type, event_type)}</span></td>"
            f"<td>{event['label']}</td><td>{event['month']}</td><td>{event['detail']}</td></tr>"
        )
    explanation_items = "\n".join(
        f"<li>{html_lib.escape(point.replace('**', ''))}</li>"
        for point in explanation_points
    )

    html = (html
        .replace("__TITLE__", f"{TARGET_PRODUCT.get('name', 'Target Product')} 全球非美销量预测")
        .replace("__PRODUCT__", TARGET_PRODUCT.get("name", "unknown"))
        .replace("__VERSION__", CONFIG["forecast"].get("version", "unknown"))
        .replace("__WEIGHT_MODE__", WEIGHT_MODE)
        .replace("__Y1_P10__", fmt(sum(g_v2_p10[:12])))
        .replace("__Y1_P50__", fmt(sum(g_v2_p50[:12])))
        .replace("__Y1_P90__", fmt(sum(g_v2_p90[:12])))
        .replace("__PEAK_M__", str(peak_row["M"]))
        .replace("__PEAK_CAL__", peak_row["cal"])
        .replace("__PEAK_VALUE__", fmt(g_v2_p50[peak_idx]))
        .replace("__ANCHOR_ROWS__", "\n".join(anchor_rows))
        .replace("__EXPLANATION_ITEMS__", explanation_items)
        .replace("__KEY_ROWS__", "\n".join(key_rows))
        .replace("__TIMELINE_ROWS__", "\n".join(timeline_rows))
        .replace("__MANUAL_MULT__", f"{manual_mult_mid:.2f}")
        .replace("__AUTO_MULT__", f"{auto_mult_mid:.2f}")
        .replace("__MC_P10__", f"{mult_p10:.2f}")
        .replace("__MC_P50__", f"{mult_p50:.2f}")
        .replace("__MC_P90__", f"{mult_p90:.2f}")
        .replace("__MC_P10_NUM__", f"{mult_p10:.6f}")
        .replace("__MC_P50_NUM__", f"{mult_p50:.6f}")
        .replace("__MC_P90_NUM__", f"{mult_p90:.6f}")
        .replace("__DATA_JSON__", json.dumps(html_data, ensure_ascii=False))
        .replace("__GENERATED_DATE__", str(CONFIG["forecast"].get("generated_date", "unknown")))
    )

    html_path = output_paths["interactive_html"]
    html_path.write_text(html)
    print(f"写入 {html_path}")
