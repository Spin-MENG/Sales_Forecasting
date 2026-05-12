def fmt_pct(value):
    return f"{value * 100:.1f}%"


def fmt_price(value):
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return "未提供"


def generate_explanation_points(
    anchor_scores,
    anchor_products,
    product_results,
    target_product,
    manual_mid_de_pct_non_us,
    auto_mid_de_pct_non_us,
    mult_p10,
    mult_p50,
    mult_p90,
    mult_dist,
):
    """Generate deterministic business-facing explanations for forecast reports."""
    sorted_anchors = sorted(anchor_scores, key=lambda item: item["auto_weight"], reverse=True)
    anchor_by_name = {item["name"]: item for item in anchor_products}
    top = sorted_anchors[0]
    top_product = anchor_by_name.get(top["name"], {})
    top_result = product_results[top["name"]]
    target_price = target_product.get("expected_avg_price") or target_product.get("msrp")

    points = [
        (
            f"本次预测主要由 **{top['name']}** 驱动，Auto 权重为 **{top['auto_weight'] * 100:.0f}%**；"
            f"该锚点的 DE/非美占比为 **{fmt_pct(top_result['de_pct_non_us'])}**。"
        ),
        (
            f"目标产品价格口径为 **{fmt_price(target_price)}**；"
            f"{top['name']} 参考价格为 **{fmt_price(_anchor_price(top_product))}**，"
            f"价格相似度得分为 **{top['product_fit_parts']['price']:.2f}**。"
        ),
        (
            f"产品相似度由品类、Wi-Fi 标准、频段、价格和定位共同决定；"
            f"{top['name']} 的 product_fit 为 **{top['score_parts']['product_fit']:.2f}**。"
        ),
        (
            f"Auto 加权 DE/非美占比为 **{fmt_pct(auto_mid_de_pct_non_us)}**，"
            f"相较 Manual 加权 **{fmt_pct(manual_mid_de_pct_non_us)}**，当前模型会使用 Auto 口径进入固定中性线。"
        ),
        (
            f"Monte Carlo 按销量口径输出 P10/P50/P90：multiplier 分别为 "
            f"**{mult_p10:.2f}x / {mult_p50:.2f}x / {mult_p90:.2f}x**；"
            f"P10 对应较高 DE 占比 **{fmt_pct(mult_dist['share_p90'])}**，P90 对应较低 DE 占比 **{fmt_pct(mult_dist['share_p10'])}**。"
        ),
        "当前区间只反映 DE/非美占比和 multiplier 不确定性，尚未叠加 DE 预测本身误差、价格折扣、广告投入、评论积累或库存约束。",
    ]

    if len(sorted_anchors) >= 2:
        second = sorted_anchors[1]
        points.insert(
            1,
            (
                f"第二参考锚点是 **{second['name']}**，Auto 权重为 **{second['auto_weight'] * 100:.0f}%**；"
                f"多个锚点共同约束 multiplier，避免单一产品历史占比主导预测。"
            ),
        )
    return points


def _anchor_price(anchor_product):
    return (
        anchor_product.get("avg_price")
        or anchor_product.get("expected_avg_price")
        or anchor_product.get("msrp")
    )
