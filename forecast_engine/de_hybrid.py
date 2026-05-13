import csv
import json
import math

from .scoring import (
    data_quality_score,
    months_between,
    normalize_factors,
    product_fit_score,
    role_score,
)
from .validation import BusinessValidationError


def get_de_forecast_mode(config):
    mode = config.get("de_forecast_model", {}).get("mode")
    if mode:
        return str(mode).lower()
    return "csv" if config.get("paths", {}).get("de_forecast_csv") else "hybrid_de"


def read_de_forecast_csv(csv_path):
    rows = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        for r in reader:
            if not r or len(r) < 11:
                continue
            if r[0].startswith("#") or r[0] in ("M", "", "cum_Y1", "cum_M18"):
                continue
            try:
                rows.append({
                    "M": int(r[0]),
                    "cal": r[1],
                    "v1_low": float(r[2]),
                    "v1_mid": float(r[3]),
                    "v1_high": float(r[4]),
                    "v2_low": float(r[5]),
                    "v2_mid": float(r[6]),
                    "v2_high": float(r[7]),
                    "v3_low": float(r[8]),
                    "v3_mid": float(r[9]),
                    "v3_high": float(r[10]),
                })
            except (ValueError, IndexError):
                continue
    if not rows:
        raise BusinessValidationError(f"{csv_path} 没有可读取的 DE 月度预测。")
    return rows


def generate_hybrid_de_forecast(config, target_product, resolve_path_fn):
    model = config.get("de_forecast_model", {})
    state_path = model.get("state_json") or config.get("paths", {}).get("de_anchor_state_json")
    if not state_path:
        raise BusinessValidationError("hybrid_de 模式缺少 de_forecast_model.state_json，无法读取 DE 锚点销量纪录。")

    state_path = resolve_path_fn(state_path)
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    launch = model.get("launch_month") or target_product.get("launch_date")
    if not launch:
        raise BusinessValidationError("hybrid_de 模式缺少 launch_month / target_product.launch_date，无法生成预测月份。")

    recent_n = int(model.get("recent_n", 6))
    horizon = int(model.get("horizon_months", 18))
    error_band = float(model.get("error_band", 0.15))
    steady_anchors = model.get("steady_anchors") or []
    if not steady_anchors:
        raise BusinessValidationError("hybrid_de 模式缺少 steady_anchors，无法计算 DE 稳态。")

    steady_weighting = model.get("steady_weighting") or {}
    steady, contributions, weighting_mode = compute_steady(
        state,
        steady_anchors,
        recent_n,
        target_product,
        steady_weighting,
    )
    seasonal = {int(k): float(v) for k, v in (model.get("seasonal") or default_seasonal()).items()}
    pulse = {int(k): float(v) for k, v in (model.get("pulse") or default_pulse()).items()}
    opening = model.get("opening", {})
    bass = model.get("bass", {})

    series = {}
    for scenario in ("v1", "v2", "v3"):
        series[scenario] = generate_monthly_series(
            steady=steady[scenario],
            launch=launch,
            horizon=horizon,
            bass_p=float(bass.get("p", 0.0085)),
            bass_q=float(bass.get("q", 0.18)),
            opening_alpha=float(opening.get("alpha", 0.42)),
            opening_tau_peak=float(opening.get("tau_peak", 3.0)),
            seasonal=seasonal,
            pulse=pulse,
        )

    rows = []
    for i in range(horizon):
        rows.append({
            "M": i + 1,
            "cal": add_months(launch, i),
            "v1_low": series["v1"][i] * (1 - error_band),
            "v1_mid": series["v1"][i],
            "v1_high": series["v1"][i] * (1 + error_band),
            "v2_low": series["v2"][i] * (1 - error_band),
            "v2_mid": series["v2"][i],
            "v2_high": series["v2"][i] * (1 + error_band),
            "v3_low": series["v3"][i] * (1 - error_band),
            "v3_mid": series["v3"][i],
            "v3_high": series["v3"][i] * (1 + error_band),
        })

    diagnostics = {
        "state_json": str(state_path),
        "steady": steady,
        "contributions": contributions,
        "weighting_mode": weighting_mode,
        "recent_n": recent_n,
        "horizon_months": horizon,
        "launch_month": launch,
        "bass": {
            "p": float(bass.get("p", 0.0085)),
            "q": float(bass.get("q", 0.18)),
        },
        "opening": {
            "alpha": float(opening.get("alpha", 0.42)),
            "tau_peak": float(opening.get("tau_peak", 3.0)),
        },
    }
    return rows, diagnostics


def compute_steady(state, steady_anchors, recent_n, target_product, weighting_config):
    steady = {"v1": 0.0, "v2": 0.0, "v3": 0.0}
    weighting_mode = str((weighting_config or {}).get("mode", "auto")).lower()
    if weighting_mode not in ("auto", "manual"):
        raise BusinessValidationError("de_forecast_model.steady_weighting.mode 只能是 auto 或 manual。")

    prepared = []
    for anchor in steady_anchors:
        monthly = get_monthly_series(state, anchor.get("source", "anchors"), anchor["key"])
        avg, n_months, start_month, end_month = avg_recent_with_window(monthly, recent_n)
        if n_months <= 0:
            label = anchor.get("label") or anchor["key"]
            raise BusinessValidationError(f"DE 稳态锚点 {label} 没有可用德国月销，无法计算近 {recent_n} 月均。")
        prepared.append({
            "anchor": anchor,
            "avg_recent": avg,
            "n_months": n_months,
            "start_month": start_month,
            "end_month": end_month,
        })

    weights = calculate_steady_anchor_weights(prepared, target_product, weighting_config, weighting_mode)
    contributions = []
    for item in prepared:
        anchor = item["anchor"]
        weight_info = weights[anchor["key"]]
        weight = weight_info["weight"]
        v1_factor = float(anchor.get("v1_factor"))
        v2_factor = float(anchor.get("v2_factor"))
        v3_factor = float(anchor.get("v3_factor"))
        avg = item["avg_recent"]
        c1 = avg * weight * v1_factor
        c2 = avg * weight * v2_factor
        c3 = avg * weight * v3_factor
        steady["v1"] += c1
        steady["v2"] += c2
        steady["v3"] += c3
        contributions.append({
            "label": anchor.get("label", anchor["key"]),
            "key": anchor["key"],
            "source": anchor.get("source", "anchors"),
            "avg_recent": avg,
            "n_months": item["n_months"],
            "start_month": item["start_month"],
            "end_month": item["end_month"],
            "weight": weight,
            "manual_weight": weight_info["manual_weight"],
            "auto_weight": weight_info["auto_weight"],
            "auto_score": weight_info["auto_score"],
            "score_parts": weight_info["score_parts"],
            "product_fit_parts": weight_info["product_fit_parts"],
            "v1_factor": v1_factor,
            "v2_factor": v2_factor,
            "v3_factor": v3_factor,
            "v2_contribution": c2,
        })
    if steady["v2"] <= 0:
        raise BusinessValidationError("DE hybrid 稳态 V2 不大于 0，请检查 steady_anchors 的销量、权重和相对系数。")
    return steady, contributions, weighting_mode


def calculate_steady_anchor_weights(prepared, target_product, weighting_config, weighting_mode):
    if weighting_mode == "manual":
        total = sum(float(item["anchor"].get("weight", 0)) for item in prepared)
        if total <= 0:
            raise BusinessValidationError("DE 稳态 manual 权重合计不大于 0，请检查 steady_anchors.weight。")
        return {
            item["anchor"]["key"]: {
                "weight": float(item["anchor"].get("weight", 0)) / total,
                "manual_weight": float(item["anchor"].get("weight", 0)),
                "auto_weight": None,
                "auto_score": None,
                "score_parts": {},
                "product_fit_parts": {},
            }
            for item in prepared
        }

    factors = normalize_factors((weighting_config or {}).get("factors", {}))
    product_fit_factors = (weighting_config or {}).get("product_fit_factors", {})
    latest_end_month = max(item["end_month"] for item in prepared if item["end_month"])

    scored = []
    for item in prepared:
        anchor = item["anchor"]
        recency_months = max(0, months_between(latest_end_month, item["end_month"]))
        product_fit, product_fit_parts = product_fit_score(target_product, anchor, product_fit_factors)
        score_parts = {
            "role": role_score(anchor.get("role")),
            "product_fit": product_fit,
            "recency": math.exp(-recency_months / 18),
            "sample_window": min(1.0, math.sqrt(item["n_months"] / 12)),
            "data_quality": data_quality_score(anchor.get("data_source")),
        }
        auto_score = sum(score_parts[k] * factors[k] for k in factors)
        scored.append({
            "key": anchor["key"],
            "manual_weight": anchor.get("weight"),
            "auto_score": auto_score,
            "score_parts": score_parts,
            "product_fit_parts": product_fit_parts,
        })

    score_sum = sum(item["auto_score"] for item in scored)
    if score_sum <= 0:
        raise BusinessValidationError("DE 稳态 auto 权重分数合计不大于 0，请检查 steady_anchors。")
    out = {}
    for item in scored:
        auto_weight = item["auto_score"] / score_sum
        out[item["key"]] = {
            "weight": auto_weight,
            "manual_weight": None if item["manual_weight"] is None else float(item["manual_weight"]),
            "auto_weight": auto_weight,
            "auto_score": item["auto_score"],
            "score_parts": item["score_parts"],
            "product_fit_parts": item["product_fit_parts"],
        }
    return out


def get_monthly_series(state, source, key):
    source = str(source or "anchors").lower()
    if source == "anchors":
        node = state.get("anchors", {}).get(key)
        field = "monthly_de_amazon"
    elif source in ("competitors", "competitors_keepa", "keepa"):
        node = state.get("competitors_keepa", {}).get(key)
        field = "monthly"
    else:
        raise BusinessValidationError(f"DE 锚点 source={source} 不支持；请使用 anchors 或 competitors。")
    if not node or field not in node:
        raise BusinessValidationError(f"DE 锚点 {key} 在 state_json 中不存在，无法读取德国月销。")
    return node[field]


def avg_recent(monthly, recent_n):
    avg, _, _, _ = avg_recent_with_window(monthly, recent_n)
    return avg


def avg_recent_with_window(monthly, recent_n):
    items = sorted((ym, float(v)) for ym, v in monthly.items() if float(v or 0) > 0)
    if not items:
        return 0.0, 0, None, None
    recent = items[-recent_n:] if len(items) >= recent_n else items
    return sum(v for _, v in recent) / len(recent), len(recent), recent[0][0], recent[-1][0]


def generate_monthly_series(*, steady, launch, horizon, bass_p, bass_q, opening_alpha, opening_tau_peak, seasonal, pulse):
    y1 = steady * 12
    f12 = bass_cdf(12, bass_p, bass_q)
    market_m = y1 / f12
    first_12 = make_sub_a(market_m, steady, launch, 12, bass_p, bass_q, opening_alpha, opening_tau_peak, seasonal, pulse)
    ratio = y1 / sum(first_12)
    raw = make_sub_a(market_m, steady, launch, horizon, bass_p, bass_q, opening_alpha, opening_tau_peak, seasonal, pulse)
    return [v * ratio for v in raw]


def make_sub_a(market_m, steady, launch, n_months, bass_p, bass_q, opening_alpha, opening_tau_peak, seasonal, pulse):
    pulse_scale = steady / 175.0
    out = []
    for i in range(n_months):
        t = i + 1
        ym = add_months(launch, i)
        cal_m = int(ym[5:])
        bass_v = market_m * (bass_cdf(t, bass_p, bass_q) - bass_cdf(t - 1, bass_p, bass_q))
        opening_v = opening_curve(t, opening_alpha, opening_tau_peak) * steady
        out.append(max(0, (bass_v + opening_v) * seasonal[cal_m] + pulse.get(cal_m, 0) * pulse_scale))
    return out


def bass_cdf(t, p, q):
    e = math.exp(-(p + q) * t)
    return (1 - e) / (1 + (q / p) * e)


def opening_curve(t, alpha, tau_peak):
    return alpha * (t / tau_peak) * math.exp(1 - t / tau_peak)


def add_months(ym, n):
    y, month = int(ym[:4]), int(ym[5:])
    month += n
    while month > 12:
        y += 1
        month -= 12
    while month < 1:
        y -= 1
        month += 12
    return f"{y:04d}-{month:02d}"


def default_seasonal():
    return {1: 0.92, 2: 0.95, 3: 1.05, 4: 0.97, 5: 0.99, 6: 1.00,
            7: 1.28, 8: 0.97, 9: 0.97, 10: 1.10, 11: 1.15, 12: 1.02}


def default_pulse():
    return {11: 20, 10: 10, 7: 30, 3: 3, 1: -3, 2: -1}
