import math


def month_index(month_text):
    year, month = str(month_text).split("-")
    return int(year) * 12 + int(month)


def months_between(later_month, earlier_month):
    return month_index(later_month) - month_index(earlier_month)


def tokenize_category(value):
    return {token for token in str(value or "").lower().replace("-", "_").split("_") if token}


def category_similarity(target_category, anchor_category):
    target_tokens = tokenize_category(target_category)
    anchor_tokens = tokenize_category(anchor_category)
    if not target_tokens or not anchor_tokens:
        return 0.6
    overlap = len(target_tokens & anchor_tokens)
    union = len(target_tokens | anchor_tokens)
    return overlap / union if union else 0.6


def role_score(role):
    role_scores = {
        "direct_predecessor_recent": 1.00,
        "direct_predecessor": 0.95,
        "direct_predecessor_history": 0.85,
        "same_generation_high_end": 0.75,
        "same_generation": 0.75,
        "adjacent_reference": 0.55,
        "competitor": 0.50,
    }
    return role_scores.get(str(role or "").lower(), 0.60)


def data_quality_score(data_source):
    data_scores = {
        "internal_sales": 1.00,
        "seller_central": 0.90,
        "keepa_estimate": 0.65,
        "manual_estimate": 0.45,
    }
    return data_scores.get(str(data_source or "").lower(), 0.70)


def exact_match_score(target_value, anchor_value, missing_default=0.6):
    if target_value in (None, "") or anchor_value in (None, ""):
        return missing_default
    return 1.0 if str(target_value).lower() == str(anchor_value).lower() else 0.0


def wifi_standard_score(target_value, anchor_value):
    target = str(target_value or "").lower()
    anchor = str(anchor_value or "").lower()
    if not target or not anchor:
        return 0.6
    if target == anchor:
        return 1.0
    wifi_order = {"wifi5": 5, "wifi6": 6, "wifi6e": 6.5, "wifi7": 7}
    if target in wifi_order and anchor in wifi_order:
        gap = abs(wifi_order[target] - wifi_order[anchor])
        return max(0.25, 1 - gap * 0.25)
    return 0.5


def price_similarity(target_product, anchor_product):
    target_price = target_product.get("expected_avg_price") or target_product.get("msrp")
    anchor_price = anchor_product.get("avg_price") or anchor_product.get("msrp")
    if not target_price or not anchor_price:
        return 0.6
    return math.exp(-abs(math.log(float(target_price) / float(anchor_price))))


def product_fit_score(target_product, anchor_product, product_fit_factors):
    default = {
        "category": 0.10,
        "wifi_standard": 0.25,
        "band_type": 0.25,
        "price": 0.25,
        "positioning": 0.15,
    }
    factors = {**default, **(product_fit_factors or {})}
    total = sum(float(v) for v in factors.values())
    if total <= 0:
        raise ValueError("product_fit_factors must sum to a positive number")
    factors = {k: float(v) / total for k, v in factors.items()}
    parts = {
        "category": category_similarity(target_product.get("category"), anchor_product.get("category")),
        "wifi_standard": wifi_standard_score(target_product.get("wifi_standard"), anchor_product.get("wifi_standard")),
        "band_type": exact_match_score(target_product.get("band_type"), anchor_product.get("band_type")),
        "price": price_similarity(target_product, anchor_product),
        "positioning": exact_match_score(target_product.get("positioning"), anchor_product.get("positioning")),
    }
    total_score = sum(parts[k] * factors[k] for k in factors)
    return total_score, parts


def normalize_factors(factors):
    default = {
        "role": 0.30,
        "product_fit": 0.35,
        "recency": 0.15,
        "sample_window": 0.10,
        "data_quality": 0.10,
    }
    merged = {**default, **(factors or {})}
    total = sum(float(v) for v in merged.values())
    if total <= 0:
        raise ValueError("anchor_weighting factors must sum to a positive number")
    return {k: float(v) / total for k, v in merged.items()}


def calculate_anchor_scores(anchor_products, product_results, target_product, weighting_config):
    factors = normalize_factors((weighting_config or {}).get("factors", {}))
    product_fit_factors = (weighting_config or {}).get("product_fit_factors", {})
    latest_end_month = max(product_results[p["name"]]["end_month"] for p in anchor_products)

    scored = []
    for product in anchor_products:
        result = product_results[product["name"]]
        recency_months = max(0, months_between(latest_end_month, result["end_month"]))
        product_fit, product_fit_parts = product_fit_score(target_product, product, product_fit_factors)
        scores = {
            "role": role_score(product.get("role")),
            "product_fit": product_fit,
            "recency": math.exp(-recency_months / 18),
            "sample_window": min(1.0, math.sqrt(result["n_months"] / 12)),
            "data_quality": data_quality_score(product.get("data_source")),
        }
        total_score = sum(scores[k] * factors[k] for k in factors)
        scored.append({
            "name": product["name"],
            "manual_weight": float(product["weight"]),
            "auto_score": total_score,
            "score_parts": scores,
            "product_fit_parts": product_fit_parts,
        })

    score_sum = sum(item["auto_score"] for item in scored)
    if score_sum <= 0:
        raise ValueError("Auto anchor scores must sum to a positive number")
    for item in scored:
        item["auto_weight"] = item["auto_score"] / score_sum
    return scored

