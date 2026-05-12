from pathlib import Path

import yaml

from .validation import BusinessValidationError


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    validate_config(config)
    return config


def validate_config(config):
    errors = []
    required_top_keys = ["paths", "excel", "monte_carlo", "forecast"]
    missing = [k for k in required_top_keys if k not in config]
    if missing:
        errors.append(f"配置文件缺少必要区块：{', '.join(missing)}。")
    anchor_products = get_anchor_products(config)
    if len(anchor_products) < 2:
        errors.append("锚点产品少于 2 个，无法形成稳定的历史参照；请至少提供 2 个 anchor_products。")

    target_product = get_target_product(config)
    _validate_product_fields(errors, target_product, "目标产品")
    de_mode = _get_de_forecast_mode(config)
    if de_mode not in ("csv", "hybrid_de"):
        errors.append("de_forecast_model.mode 只能是 csv 或 hybrid_de。")
    if de_mode == "csv" and not config.get("paths", {}).get("de_forecast_csv"):
        errors.append("DE 预测模式为 csv，但 paths.de_forecast_csv 为空。")
    if de_mode == "hybrid_de":
        de_model = config.get("de_forecast_model", {})
        if not (de_model.get("state_json") or config.get("paths", {}).get("de_anchor_state_json")):
            errors.append("DE 预测模式为 hybrid_de，但缺少 de_forecast_model.state_json。")
        if not (de_model.get("launch_month") or target_product.get("launch_date")):
            errors.append("DE 预测模式为 hybrid_de，但缺少 launch_month / target_product.launch_date。")
        if not de_model.get("steady_anchors"):
            errors.append("DE 预测模式为 hybrid_de，但缺少 steady_anchors。")
        for idx, anchor in enumerate(de_model.get("steady_anchors") or [], start=1):
            label = anchor.get("label") or anchor.get("key") or f"DE 稳态锚点 {idx}"
            for field in ("key", "weight", "v1_factor", "v2_factor", "v3_factor"):
                if field not in anchor:
                    errors.append(f"{label} 缺少 {field}，无法计算 DE 稳态。")

    total_weight = 0
    for idx, product in enumerate(anchor_products, start=1):
        product_name = product.get("name") or f"第 {idx} 个锚点产品"
        _validate_product_fields(errors, product, product_name)
        if not product.get("file") and not product.get("region_sales_file"):
            errors.append(f"{product_name} 没有配置销量文件 file / region_sales_file，无法读取区域销量。")
        if product.get("start_month") and product.get("end_month") and product["start_month"] > product["end_month"]:
            errors.append(f"{product_name} 的 start_month 晚于 end_month，请检查历史窗口。")
        try:
            total_weight += float(product.get("weight", 0))
        except (TypeError, ValueError):
            errors.append(f"{product_name} 的 weight 不是数字；当前脚本仍需要提供数值权重。")

    if anchor_products and total_weight <= 0:
        errors.append("锚点产品权重合计不大于 0，请检查 anchor_products.weight。")

    if errors:
        raise BusinessValidationError(errors)


def get_anchor_products(config):
    return config.get("anchor_products") or config.get("products") or []


def get_target_product(config):
    return config.get("target_product") or {
        "name": config.get("forecast", {}).get("product", "unknown"),
        "target_regions": config.get("forecast", {}).get("regions", []),
    }


def _validate_product_fields(errors, product, label):
    if not product.get("category"):
        errors.append(f"{label} 缺少 category，无法计算产品相似度。")
    if not product.get("wifi_standard"):
        errors.append(f"{label} 缺少 wifi_standard，无法计算 Wi-Fi 标准相似度。")
    if not (product.get("avg_price") or product.get("expected_avg_price") or product.get("msrp")):
        errors.append(f"{label} 缺少价格字段 avg_price / expected_avg_price / msrp，无法计算价格相似度。")


def resolve_path(path_value, base_dir=None):
    path = Path(path_value)
    if path.is_absolute():
        return path
    if base_dir is None:
        return path
    return Path(base_dir) / path


def _get_de_forecast_mode(config):
    mode = config.get("de_forecast_model", {}).get("mode")
    if mode:
        return str(mode).lower()
    return "csv" if config.get("paths", {}).get("de_forecast_csv") else "hybrid_de"
