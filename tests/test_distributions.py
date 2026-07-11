import random

import pytest

from core.distributions import (
    Beta,
    Distribution,
    Empirical,
    Exponential,
    Gamma,
    LogNormal,
    Normal,
    Pareto,
    Triangular,
    TriangularInverse,
    Uniform,
    Weibull,
)


def test_exponential_mean_converges():
    random.seed(42)
    d = Exponential(mean=5.0)
    samples = [d.sample() for _ in range(2000)]
    assert all(s >= 0 for s in samples)
    assert abs(sum(samples) / len(samples) - 5.0) < 0.5


def test_exponential_zero_mean_is_instant():
    d = Exponential(mean=0)
    assert d.sample() == 0.0


def test_uniform_stays_within_bounds():
    d = Uniform(a=2.0, b=8.0)
    for _ in range(500):
        s = d.sample()
        assert 2.0 <= s <= 8.0


def test_uniform_rejects_invalid_bounds():
    with pytest.raises(ValueError):
        Uniform(a=10.0, b=1.0)


def test_triangular_stays_within_bounds():
    d = Triangular(low=1.0, mode=3.0, high=6.0)
    for _ in range(500):
        s = d.sample()
        assert 1.0 <= s <= 6.0


def test_triangular_rejects_invalid_mode():
    with pytest.raises(ValueError):
        Triangular(low=5.0, mode=1.0, high=6.0)


def test_normal_floors_at_zero_by_default():
    d = Normal(mu=-10.0, sigma=1.0)
    samples = [d.sample() for _ in range(200)]
    assert all(s >= 0 for s in samples)


def test_normal_can_disable_floor():
    d = Normal(mu=-10.0, sigma=0.001, floor_at_zero=False)
    assert d.sample() < 0


def test_empirical_returns_only_known_values():
    d = Empirical(values=[1.0, 2.0, 3.0], cum_probs=[0.3, 0.7, 1.0])
    samples = {d.sample() for _ in range(200)}
    assert samples.issubset({1.0, 2.0, 3.0})


def test_empirical_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        Empirical(values=[1.0, 2.0], cum_probs=[1.0])


def test_empirical_rejects_bad_final_prob():
    with pytest.raises(ValueError):
        Empirical(values=[1.0, 2.0], cum_probs=[0.5, 0.9])


def test_from_spec_builds_correct_type():
    d = Distribution.from_spec("exp", {"mean": 4.0})
    assert isinstance(d, Exponential)

    d2 = Distribution.from_spec("Triangular", {"low": 1, "mode": 2, "high": 3})
    assert isinstance(d2, Triangular)


def test_from_spec_rejects_unknown_kind():
    with pytest.raises(ValueError):
        Distribution.from_spec("poisson", {})


def test_triangular_inverse_stays_within_bounds():
    d = TriangularInverse(low=1.0, mode=3.0, high=6.0)
    for _ in range(500):
        s = d.sample()
        assert 1.0 <= s <= 6.0


def test_triangular_inverse_rejects_invalid_mode():
    with pytest.raises(ValueError):
        TriangularInverse(low=5.0, mode=1.0, high=6.0)


def test_lognormal_samples_are_non_negative():
    d = LogNormal(mean=0.0, sigma=1.0)
    samples = [d.sample() for _ in range(200)]
    assert all(s >= 0 for s in samples)


def test_lognormal_floor_at_zero_has_no_effect_since_always_nonnegative():
    d = LogNormal(mean=0.0, sigma=1.0, floor_at_zero=False)
    samples = [d.sample() for _ in range(200)]
    assert all(s >= 0 for s in samples)


def test_beta_stays_within_unit_interval():
    d = Beta(a=2.0, b=5.0)
    for _ in range(500):
        s = d.sample()
        assert 0.0 <= s <= 1.0


def test_beta_rejects_non_positive_params():
    with pytest.raises(ValueError):
        Beta(a=0, b=5)
    with pytest.raises(ValueError):
        Beta(a=5, b=-1)


def test_gamma_samples_are_non_negative():
    d = Gamma(alpha=2.0, beta=3.0)
    samples = [d.sample() for _ in range(500)]
    assert all(s >= 0 for s in samples)


def test_gamma_rejects_non_positive_params():
    with pytest.raises(ValueError):
        Gamma(alpha=0, beta=3)
    with pytest.raises(ValueError):
        Gamma(alpha=2, beta=-1)


def test_weibull_samples_are_non_negative():
    d = Weibull(a=1.5)
    samples = [d.sample() for _ in range(500)]
    assert all(s >= 0 for s in samples)


def test_weibull_rejects_non_positive_shape():
    with pytest.raises(ValueError):
        Weibull(a=0)
    with pytest.raises(ValueError):
        Weibull(a=-1)


def test_pareto_samples_are_non_negative():
    d = Pareto(a=2.0)
    samples = [d.sample() for _ in range(500)]
    assert all(s >= 0 for s in samples)


def test_pareto_rejects_non_positive_shape():
    with pytest.raises(ValueError):
        Pareto(a=0)
    with pytest.raises(ValueError):
        Pareto(a=-2)


def test_from_spec_builds_all_new_distribution_types():
    cases = [
        ("triangularInverse", {"low": 1, "mode": 2, "high": 5}, TriangularInverse),
        ("logNormal", {"mean": 0.0, "sigma": 1.0}, LogNormal),
        ("beta", {"a": 2.0, "b": 5.0}, Beta),
        ("gamma", {"alpha": 2.0, "beta": 3.0}, Gamma),
        ("weibull", {"a": 1.5}, Weibull),
        ("pareto", {"a": 2.0}, Pareto),
        ("parento", {"a": 2.0}, Pareto),  # alias por typo histórico
    ]
    for kind, params, expected_type in cases:
        d = Distribution.from_spec(kind, params)
        assert isinstance(d, expected_type)


def test_from_spec_normalizes_case_and_whitespace_for_new_kinds():
    d = Distribution.from_spec(" TriangularInverse ", {"low": 1, "mode": 2, "high": 5})
    assert isinstance(d, TriangularInverse)

    d2 = Distribution.from_spec("LOGNORMAL", {"mean": 0.0, "sigma": 1.0})
    assert isinstance(d2, LogNormal)
