"""
新品全球（除美国外）销量预测工具。

基于配置中的 DE 月度三档预测，按锚点产品的 "DE / 非美全球" 销售占比反推。
"""
import argparse
import csv
import sys
from pathlib import Path

from forecast_engine.anchors import extract_country_totals
from forecast_engine.config import (
    get_anchor_products,
    get_target_product,
    load_config,
    resolve_path,
)
from forecast_engine.monte_carlo import simulate_multiplier_distribution
from forecast_engine.scoring import calculate_anchor_scores
from forecast_engine.reports import build_output_paths, get_output_settings, write_reports
from forecast_engine.validation import BusinessValidationError

def parse_args():
    parser = argparse.ArgumentParser(description="New product global ex-US forecast model")
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="YAML config path. Copy forecast_config_template.yaml and fill it before running.",
    )
    return parser.parse_args()

def main():
    args = parse_args()
    CONFIG_PATH = args.config
    CONFIG = load_config(CONFIG_PATH)
    ANCHOR_PRODUCTS = get_anchor_products(CONFIG)
    TARGET_PRODUCT = get_target_product(CONFIG)
    OUT = resolve_path(CONFIG["paths"]["output_dir"])
    BASE = resolve_path(CONFIG["paths"]["base_data_dir"])
    DE_FORECAST_CSV = resolve_path(CONFIG["paths"]["de_forecast_csv"])
    N_MONTE_CARLO = int(CONFIG["monte_carlo"].get("n", 20000))
    RANDOM_SEED = int(CONFIG["monte_carlo"].get("seed", 7200))
    SHARE_CLIP_MIN = float(CONFIG["monte_carlo"].get("share_clip_min", 0.05))
    SHARE_CLIP_MAX = float(CONFIG["monte_carlo"].get("share_clip_max", 0.45))
    ANCHOR_WEIGHTING = CONFIG.get("anchor_weighting", {"mode": "manual"})
    WEIGHT_MODE = str(ANCHOR_WEIGHTING.get("mode", "manual")).lower()
    if WEIGHT_MODE not in ("manual", "auto"):
        raise ValueError("anchor_weighting.mode must be manual or auto")
    REGIONS = CONFIG["forecast"].get("regions", [])
    TIMELINE_EVENTS = CONFIG["forecast"].get("timeline_events", [])
    
    print("="*70)
    print("配置")
    print("="*70)
    print(f"读取配置: {CONFIG_PATH}")
    print(f"目标产品: {TARGET_PRODUCT.get('name', 'unknown')}")
    print(f"输出目录: {OUT}")
    print(f"DE forecast: {DE_FORECAST_CSV}")
    print(f"预测范围区域: {', '.join(TARGET_PRODUCT.get('target_regions') or REGIONS)}")
    print(f"锚点权重模式: {WEIGHT_MODE}")
    
    print("\n" + "="*70)
    print("第一步：计算 GL 旧品 DE / 非美全球 占比")
    print("="*70)
    product_results = {}
    for product in ANCHOR_PRODUCTS:
        product_file = resolve_path(product.get("file") or product.get("region_sales_file"), BASE)
        result = extract_country_totals(
            product_file,
            product.get("label", product["name"]),
            CONFIG["excel"],
            start_month=product.get("start_month"),
            end_month=product.get("end_month"),
        )
        product_results[product["name"]] = result
    
    anchor_scores = calculate_anchor_scores(ANCHOR_PRODUCTS, product_results, TARGET_PRODUCT, ANCHOR_WEIGHTING)
    score_by_name = {item["name"]: item for item in anchor_scores}
    
    print("\n自动锚点评分:")
    print("  产品 | manual_w | auto_w | score | role/product_fit/recency/window/data")
    for item in anchor_scores:
        parts = item["score_parts"]
        print(
            f"  {item['name']} | {item['manual_weight']:.2f} | {item['auto_weight']:.2f} | "
            f"{item['auto_score']:.3f} | "
            f"{parts['role']:.2f}/{parts['product_fit']:.2f}/{parts['recency']:.2f}/{parts['sample_window']:.2f}/{parts['data_quality']:.2f}"
        )
    
    manual_share_points = []
    auto_share_points = []
    for product in ANCHOR_PRODUCTS:
        result = product_results[product["name"]]
        manual_share_points.append({
            "label": product["name"],
            "de_pct_non_us": result["de_pct_non_us"],
            "de_pct_global": result["de_pct_global"],
            "weight": float(product["weight"]),
        })
        auto_share_points.append({
            "label": product["name"],
            "de_pct_non_us": result["de_pct_non_us"],
            "de_pct_global": result["de_pct_global"],
            "weight": score_by_name[product["name"]]["auto_weight"],
        })
    
    share_points = auto_share_points if WEIGHT_MODE == "auto" else manual_share_points
    
    weight_sum = sum(p["weight"] for p in share_points)
    mid_de_pct_non_us = sum(p["weight"] * p["de_pct_non_us"] for p in share_points) / weight_sum
    mid_de_pct_global = sum(p["weight"] * p["de_pct_global"] for p in share_points) / weight_sum
    manual_mid_de_pct_non_us = sum(p["weight"] * p["de_pct_non_us"] for p in manual_share_points) / sum(p["weight"] for p in manual_share_points)
    auto_mid_de_pct_non_us = sum(p["weight"] * p["de_pct_non_us"] for p in auto_share_points) / sum(p["weight"] for p in auto_share_points)
    manual_mult_mid = 1 / manual_mid_de_pct_non_us
    auto_mult_mid = 1 / auto_mid_de_pct_non_us
    
    sorted_share_points = sorted(share_points, key=lambda p: p["de_pct_non_us"])
    low_share_point = sorted_share_points[-1]
    high_share_point = sorted_share_points[0]
    
    mult_mid = 1 / mid_de_pct_non_us
    mult_low = 1 / low_share_point["de_pct_non_us"]
    mult_high = 1 / high_share_point["de_pct_non_us"]
    mult_dist = simulate_multiplier_distribution(
        share_points,
        n=N_MONTE_CARLO,
        seed=RANDOM_SEED,
        clip_min=SHARE_CLIP_MIN,
        clip_max=SHARE_CLIP_MAX,
    )
    mult_p10 = mult_dist["mult_p10"]
    mult_p50 = mult_dist["mult_p50"]
    mult_p90 = mult_dist["mult_p90"]
    
    print("\n" + "="*70)
    print("第二步：综合反推系数")
    print("="*70)
    print(f"权重模式 = {WEIGHT_MODE}")
    print(f"  manual 加权 DE / 非美 = {manual_mid_de_pct_non_us*100:.2f}% → multiplier {manual_mult_mid:.2f}×")
    print(f"  auto   加权 DE / 非美 = {auto_mid_de_pct_non_us*100:.2f}% → multiplier {auto_mult_mid:.2f}×")
    print(f"加权 DE / 非美 = {mid_de_pct_non_us*100:.2f}%")
    print(f"反推系数:")
    print(f"  保守 (low_mult,  DE占比 {low_share_point['de_pct_non_us']*100:.1f}%, {low_share_point['label']}) = {mult_low:.2f}×")
    print(f"  中性 (mid_mult,  DE占比 {mid_de_pct_non_us*100:.1f}%) = {mult_mid:.2f}×")
    print(f"  乐观 (high_mult, DE占比 {high_share_point['de_pct_non_us']*100:.1f}%, {high_share_point['label']}) = {mult_high:.2f}×")
    print(f"Monte Carlo multiplier 分布（n={N_MONTE_CARLO:,}, seed={RANDOM_SEED}）:")
    print(f"  原始 DE占比分位 P10/P50/P90 = {mult_dist['share_p10']*100:.1f}% / {mult_dist['share_p50']*100:.1f}% / {mult_dist['share_p90']*100:.1f}%")
    print(f"  销量口径 P10/P50/P90 对应 DE占比 = {mult_dist['share_p90']*100:.1f}% / {mult_dist['share_p50']*100:.1f}% / {mult_dist['share_p10']*100:.1f}%")
    print(f"  销量口径 multiplier P10/P50/P90 = {mult_p10:.2f}× / {mult_p50:.2f}× / {mult_p90:.2f}×")
    
    print("\n" + "="*70)
    print(f"第三步：读取 {CONFIG['forecast'].get('de_source_label', 'DE input')} {TARGET_PRODUCT.get('name', '目标产品')} DE 预测")
    print("="*70)
    de_forecast = []
    with open(DE_FORECAST_CSV) as f:
        reader = csv.reader(f)
        for r in reader:
            if not r or len(r) < 11: continue
            if r[0].startswith('#') or r[0] in ('M', '', 'cum_Y1', 'cum_M18'): continue
            try:
                m = int(r[0])
                de_forecast.append({
                    "M": m, "cal": r[1],
                    "v1_low": float(r[2]), "v1_mid": float(r[3]), "v1_high": float(r[4]),
                    "v2_low": float(r[5]), "v2_mid": float(r[6]), "v2_high": float(r[7]),
                    "v3_low": float(r[8]), "v3_mid": float(r[9]), "v3_high": float(r[10]),
                })
            except (ValueError, IndexError): continue
    
    print(f"读取 {len(de_forecast)} 行 {CONFIG['forecast'].get('de_source_label', 'DE input')} DE 月度预测")
    print(f"  V2_mid Y1 = {sum(r['v2_mid'] for r in de_forecast[:12]):,.0f}")
    print(f"  V2_mid M18 = {sum(r['v2_mid'] for r in de_forecast):,.0f}")
    
    print("\n" + "="*70)
    print("第四步：反推全球非美月销")
    print("="*70)
    T = len(de_forecast)
    g_v2_low = [r['v2_mid'] * mult_low for r in de_forecast]
    g_v2_mid = [r['v2_mid'] * mult_mid for r in de_forecast]
    g_v2_high = [r['v2_mid'] * mult_high for r in de_forecast]
    g_v2_p10 = [r['v2_mid'] * mult_p10 for r in de_forecast]
    g_v2_p50 = [r['v2_mid'] * mult_p50 for r in de_forecast]
    g_v2_p90 = [r['v2_mid'] * mult_p90 for r in de_forecast]
    g_v1_mid = [r['v1_mid'] * mult_mid for r in de_forecast]
    g_v3_mid = [r['v3_mid'] * mult_mid for r in de_forecast]
    
    print(f"\n{TARGET_PRODUCT.get('name', '目标产品')} 全球非美 V2 中性 月度:")
    for i, r in enumerate(de_forecast):
        print(f"  M{r['M']:>2} {r['cal']}: DE={r['v2_mid']:>5.0f} → 全球非美 P50={g_v2_p50[i]:>6.0f} (P10={g_v2_p10[i]:.0f}, P90={g_v2_p90[i]:.0f})")
    
    print(f"\n累计 Y1 (V2 中性): DE={sum(r['v2_mid'] for r in de_forecast[:12]):,.0f} → 全球非美={sum(g_v2_mid[:12]):,.0f}")
    print(f"累计 M18 (V2 中性): DE={sum(r['v2_mid'] for r in de_forecast):,.0f} → 全球非美={sum(g_v2_mid):,.0f}")
    print(f"累计 Y1 (V2 × multiplier 分布): P10={sum(g_v2_p10[:12]):,.0f}, P50={sum(g_v2_p50[:12]):,.0f}, P90={sum(g_v2_p90[:12]):,.0f}")
    print(f"累计 M18 (V2 × multiplier 分布): P10={sum(g_v2_p10):,.0f}, P50={sum(g_v2_p50):,.0f}, P90={sum(g_v2_p90):,.0f}")
    
    output_settings = get_output_settings(CONFIG, TARGET_PRODUCT)
    output_paths = build_output_paths(OUT, output_settings)
    de_source_label = output_settings["de_source_label"]

    write_reports(
        OUT=OUT,
        CONFIG_PATH=CONFIG_PATH,
        WEIGHT_MODE=WEIGHT_MODE,
        manual_mult_mid=manual_mult_mid,
        auto_mult_mid=auto_mult_mid,
        mid_de_pct_non_us=mid_de_pct_non_us,
        share_points=share_points,
        mult_low=mult_low,
        mult_mid=mult_mid,
        mult_high=mult_high,
        mult_p10=mult_p10,
        mult_p50=mult_p50,
        mult_p90=mult_p90,
        N_MONTE_CARLO=N_MONTE_CARLO,
        RANDOM_SEED=RANDOM_SEED,
        de_forecast=de_forecast,
        g_v2_low=g_v2_low,
        g_v2_mid=g_v2_mid,
        g_v2_high=g_v2_high,
        g_v2_p10=g_v2_p10,
        g_v2_p50=g_v2_p50,
        g_v2_p90=g_v2_p90,
        g_v1_mid=g_v1_mid,
        g_v3_mid=g_v3_mid,
        product_results=product_results,
        ANCHOR_PRODUCTS=ANCHOR_PRODUCTS,
        anchor_scores=anchor_scores,
        CONFIG=CONFIG,
        TARGET_PRODUCT=TARGET_PRODUCT,
        REGIONS=REGIONS,
        TIMELINE_EVENTS=TIMELINE_EVENTS,
        manual_mid_de_pct_non_us=manual_mid_de_pct_non_us,
        auto_mid_de_pct_non_us=auto_mid_de_pct_non_us,
        mult_dist=mult_dist,
        low_share_point=low_share_point,
        high_share_point=high_share_point,
        output_paths=output_paths,
        de_source_label=de_source_label,
    )
    
    print("\n" + "="*70)
    print(f"{CONFIG['forecast'].get('version', 'unknown')} 完成")
    print(f"  DE / 非美 加权 = {mid_de_pct_non_us*100:.1f}%")
    print(f"  反推系数 (中性) = {mult_mid:.2f}×")
    print(f"  V2 中性 全球非美 Y1 = {sum(g_v2_mid[:12]):,.0f}")
    print(f"  V2 中性 全球非美 M18 = {sum(g_v2_mid):,.0f}")
    print("="*70)


if __name__ == "__main__":
    try:
        main()
    except BusinessValidationError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(2)
