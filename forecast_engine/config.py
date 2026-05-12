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
