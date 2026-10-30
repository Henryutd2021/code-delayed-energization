"""Inputs of the CoDE framework: project, private, ratepayer and timing parameters.

Symbols follow the article (docs/formulation.md). Units are part of the field names:
USD, MW-IT (server and networking load), grid MW (facility load), months. Rates and
probabilities are fractions (0.08, not 8).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields, replace
from typing import Any

PROFILES = ("static", "linear", "front_loaded", "back_loaded")
FINANCING_RULES = ("milestone", "realization_linked", "explicit")


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, got {value!r}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")
    return value


def _fraction(value: Any, name: str) -> float:
    value = _finite(value, name)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1, got {value}")
    return value


def _non_negative(value: Any, name: str) -> float:
    value = _finite(value, name)
    if value < 0.0:
        raise ValueError(f"{name} must be non-negative, got {value}")
    return value


def _positive(value: Any, name: str) -> float:
    value = _finite(value, name)
    if value <= 0.0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _months(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
            or float(value) != int(value):
        raise ValueError(f"{name} must be a whole number of months, got {value!r}")
    value = int(value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative, got {value}")
    return value


@dataclass(frozen=True)
class Project:
    """Delayed load: IT capacity P_I and its conversion to grid MW and MVA."""

    it_capacity_mw: float          # P_I, MW-IT
    pue: float                     # power usage effectiveness: P_G = PUE * P_I
    power_factor: float            # pf: S = P_G / pf

    def __post_init__(self) -> None:
        _non_negative(self.it_capacity_mw, "it_capacity_mw")
        _positive(self.pue, "pue")
        pf = _positive(self.power_factor, "power_factor")
        if pf > 1.0:
            raise ValueError(f"power_factor must not exceed 1, got {pf}")

    @property
    def grid_mw(self) -> float:
        """Facility-level grid demand P_G = PUE * P_I (MW)."""
        return self.pue * self.it_capacity_mw

    @property
    def interconnection_mva(self) -> float:
        """Interconnection apparent power S = P_G / pf (MVA)."""
        return self.grid_mw / self.power_factor


@dataclass(frozen=True)
class PrivateInputs:
    """Inputs of the private perspective, Eq. (2)."""

    gross_value_usd_per_mw_it_month: float        # V
    operating_margin: float                       # mu
    realization_probability: float               # q
    substitution_fraction: float                  # s
    committed_capital_usd_per_mw_it: float        # K
    committed_capital_fraction: float             # c
    deployment_peak: float                        # a, peak level of alpha_t
    carrying_rate_annual: float                   # i
    deployment_profile: str = "static"            # shape of alpha_t
    contract_penalty_usd_per_mw_it_month: float = 0.0     # pi^contract
    mitigation_premium_usd_per_mw_it_month: float = 0.0   # pi^mit

    def __post_init__(self) -> None:
        _non_negative(self.gross_value_usd_per_mw_it_month, "gross_value_usd_per_mw_it_month")
        _fraction(self.operating_margin, "operating_margin")
        _fraction(self.realization_probability, "realization_probability")
        _fraction(self.substitution_fraction, "substitution_fraction")
        _non_negative(self.committed_capital_usd_per_mw_it, "committed_capital_usd_per_mw_it")
        _fraction(self.committed_capital_fraction, "committed_capital_fraction")
        _fraction(self.deployment_peak, "deployment_peak")
        _non_negative(self.carrying_rate_annual, "carrying_rate_annual")
        _non_negative(self.contract_penalty_usd_per_mw_it_month, "contract_penalty_usd_per_mw_it_month")
        _non_negative(self.mitigation_premium_usd_per_mw_it_month, "mitigation_premium_usd_per_mw_it_month")
        if self.deployment_profile not in PROFILES:
            raise ValueError(f"deployment_profile must be one of {PROFILES}, got {self.deployment_profile!r}")


@dataclass(frozen=True)
class RatepayerInputs:
    """Inputs of the ratepayer perspective, Eq. (3).

    ``financing_rule`` sets the upgrade-financing probability phi_u and the stranding
    probability phi_s conditional on financing:

    - ``"milestone"``: phi_u is given; phi_s = (1 - q) + q * p_a (financing follows
      contractual milestones, so non-realization strands a financed upgrade);
    - ``"realization_linked"``: phi_u = q and phi_s = p_a;
    - ``"explicit"``: phi_u and phi_s are both given.
    """

    upgrade_cost_usd_per_grid_mw: float           # U
    utility_carrying_rate_annual: float           # i_u
    residual_share: float                         # rho
    financing_rule: str = "milestone"
    financing_probability: float | None = None    # phi_u ("milestone", "explicit")
    abandonment_probability: float | None = None  # p_a ("milestone", "realization_linked")
    stranding_probability: float | None = None    # phi_s ("explicit")

    def __post_init__(self) -> None:
        _non_negative(self.upgrade_cost_usd_per_grid_mw, "upgrade_cost_usd_per_grid_mw")
        _non_negative(self.utility_carrying_rate_annual, "utility_carrying_rate_annual")
        _fraction(self.residual_share, "residual_share")
        if self.financing_rule not in FINANCING_RULES:
            raise ValueError(f"financing_rule must be one of {FINANCING_RULES}, got {self.financing_rule!r}")
        needed = {
            "milestone": ("financing_probability", "abandonment_probability"),
            "realization_linked": ("abandonment_probability",),
            "explicit": ("financing_probability", "stranding_probability"),
        }[self.financing_rule]
        for name in ("financing_probability", "abandonment_probability", "stranding_probability"):
            value = getattr(self, name)
            if name in needed:
                if value is None:
                    raise ValueError(f"financing_rule {self.financing_rule!r} needs {name}")
                _fraction(value, name)
            elif value is not None:
                raise ValueError(f"{name} is not used by financing_rule {self.financing_rule!r}; leave it unset")

    def event_probabilities(self, realization_probability: float) -> tuple[float, float]:
        """Return (phi_u, phi_s) for a realization probability q."""
        q = _fraction(realization_probability, "realization_probability")
        if self.financing_rule == "milestone":
            return float(self.financing_probability), (1.0 - q) + q * float(self.abandonment_probability)
        if self.financing_rule == "realization_linked":
            return q, float(self.abandonment_probability)
        return float(self.financing_probability), float(self.stranding_probability)


@dataclass(frozen=True)
class Scenario:
    """One delayed-energization case: a project, its inputs, the discount rate and the delay tau."""

    project: Project
    private: PrivateInputs
    ratepayer: RatepayerInputs
    discount_rate_annual: float                   # r
    delay_months: int                             # tau
    name: str = field(default="scenario")

    def __post_init__(self) -> None:
        r = _finite(self.discount_rate_annual, "discount_rate_annual")
        if r <= -1.0:
            raise ValueError("discount_rate_annual must exceed -1")
        object.__setattr__(self, "delay_months", _months(self.delay_months, "delay_months"))
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string")

    # Convenience copies used by the metrics and scenario tools.
    def with_delay(self, delay_months: int) -> "Scenario":
        return replace(self, delay_months=delay_months)

    def with_capacity(self, it_capacity_mw: float) -> "Scenario":
        return replace(self, project=replace(self.project, it_capacity_mw=it_capacity_mw))

    def with_realization(self, realization_probability: float) -> "Scenario":
        return replace(self, private=replace(self.private, realization_probability=realization_probability))

    @property
    def event_probabilities(self) -> tuple[float, float]:
        """(phi_u, phi_s) under this scenario's realization probability."""
        return self.ratepayer.event_probabilities(self.private.realization_probability)


def usd_per_kw_month_to_usd_per_mw_month(value: float) -> float:
    """Convert a market rate quoted in USD/kW-month to USD/MW-month."""
    return _finite(value, "value") * 1000.0


def _split(path: str) -> tuple[str, str | None]:
    parts = path.split(".")
    if len(parts) == 1 and parts[0] in {"delay_months", "discount_rate_annual", "name"}:
        return parts[0], None
    if len(parts) == 2 and parts[0] in {"project", "private", "ratepayer"}:
        return parts[0], parts[1]
    raise KeyError(f"unknown parameter {path!r}")


def set_parameters(scenario: Scenario, overrides: dict[str, Any]) -> Scenario:
    """Return a copy of ``scenario`` with several parameters changed at once.

    Paths are fields of :class:`Scenario` (``"delay_months"``, ``"discount_rate_annual"``,
    ``"name"``) or ``"<group>.<field>"`` with group ``project``, ``private`` or ``ratepayer``.
    The overrides of each group are applied together and validated once, so a case can
    switch, for example, the financing rule and clear the fields it no longer uses
    (``None`` unsets an optional field).
    """
    top: dict[str, Any] = {}
    groups: dict[str, dict[str, Any]] = {}
    for path, value in overrides.items():
        head, tail = _split(path)
        if tail is None:
            top[head] = value
            continue
        group = getattr(scenario, head)
        if tail not in {f.name for f in fields(group)}:
            raise KeyError(f"unknown parameter {path!r}")
        groups.setdefault(head, {})[tail] = value
    changes = {head: replace(getattr(scenario, head), **vals) for head, vals in groups.items()}
    return replace(scenario, **top, **changes)


def set_parameter(scenario: Scenario, path: str, value: Any) -> Scenario:
    """Return a copy of ``scenario`` with one parameter changed (paths as in :func:`set_parameters`)."""
    return set_parameters(scenario, {path: value})


def get_parameter(scenario: Scenario, path: str) -> Any:
    """Read one parameter by the same paths as :func:`set_parameters`."""
    head, tail = _split(path)
    if tail is None:
        return getattr(scenario, head)
    group = getattr(scenario, head)
    if tail not in {f.name for f in fields(group)}:
        raise KeyError(f"unknown parameter {path!r}")
    return getattr(group, tail)
