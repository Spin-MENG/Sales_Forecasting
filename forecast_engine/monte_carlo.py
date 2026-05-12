import math

import numpy as np


def logit(x):
    return math.log(x / (1 - x))


def inv_logit(x):
    return 1 / (1 + math.exp(-x))


def weighted_mean(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    return float(np.sum(values * weights) / np.sum(weights))


def weighted_std(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    mean = weighted_mean(values, weights)
    variance = np.sum(weights * (values - mean) ** 2) / np.sum(weights)
    return float(math.sqrt(variance))


def simulate_multiplier_distribution(share_points, n, seed, clip_min=0.05, clip_max=0.45):
    """Use historical DE/non-US shares as weighted priors and sample a bounded multiplier distribution."""
    labels = [p["label"] for p in share_points]
    shares = np.asarray([p["de_pct_non_us"] for p in share_points], dtype=float)
    weights = np.asarray([p["weight"] for p in share_points], dtype=float)
    weights = weights / weights.sum()

    logit_shares = np.asarray([logit(s) for s in shares], dtype=float)
    mu = weighted_mean(logit_shares, weights)
    sigma = max(weighted_std(logit_shares, weights), 0.01)

    rng = np.random.default_rng(seed)
    sampled_logit_shares = rng.normal(mu, sigma, size=n)
    sampled_shares = np.asarray([inv_logit(x) for x in sampled_logit_shares])
    sampled_shares = np.clip(sampled_shares, clip_min, clip_max)
    sampled_multipliers = 1 / sampled_shares

    return {
        "labels": labels,
        "shares": shares,
        "weights": weights,
        "share_p10": float(np.percentile(sampled_shares, 10)),
        "share_p50": float(np.percentile(sampled_shares, 50)),
        "share_p90": float(np.percentile(sampled_shares, 90)),
        "mult_p10": float(np.percentile(sampled_multipliers, 10)),
        "mult_p50": float(np.percentile(sampled_multipliers, 50)),
        "mult_p90": float(np.percentile(sampled_multipliers, 90)),
        "sampled_multipliers": sampled_multipliers,
    }

