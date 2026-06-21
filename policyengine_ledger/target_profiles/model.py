"""Ledger-owned target profiles and measurement contracts.

Target profiles describe which source-backed Ledger facts a calibration build
may select and how a model should measure the matching quantity on microdata.
They do not contain target values. Values come from Ledger fact rows selected by
the profile's selectors.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

TARGET_PROFILE_SCHEMA_VERSION = "policyengine_ledger.target_profile.v1"


@dataclass(frozen=True)
class TargetProfileBinding:
    """Backend-specific executable binding for one measurement contract."""

    backend: str
    metric_name: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class TargetProfileTarget:
    """One profile target family and its microdata measurement contract."""

    target_id: str
    family: str
    geography_levels: tuple[str, ...]
    ledger_selector: Mapping[str, Any]
    measurement: Mapping[str, Any]
    bindings: Mapping[str, TargetProfileBinding]
    tolerance: float | None = None

    def binding(self, backend: str) -> TargetProfileBinding:
        """Return the binding for ``backend`` or raise a useful error."""
        try:
            return self.bindings[backend]
        except KeyError:
            raise KeyError(
                f"Target profile row {self.target_id!r} has no {backend!r} binding."
            ) from None


@dataclass(frozen=True)
class TargetProfile:
    """A Ledger-owned target profile consumed by Populace or other solvers."""

    profile_id: str
    country: str
    label: str
    base_period_policy: str
    default_operation: str
    targets: tuple[TargetProfileTarget, ...]

    def targets_for_geography(
        self,
        geography_level: str,
    ) -> tuple[TargetProfileTarget, ...]:
        """Return profile rows active for a geography level."""
        return tuple(
            target
            for target in self.targets
            if geography_level in target.geography_levels
        )


def load_target_profile(profile_id: str) -> TargetProfile:
    """Load a packaged Ledger target profile by ID."""
    if not profile_id or "/" in profile_id or "\\" in profile_id:
        raise ValueError(f"Invalid target profile id {profile_id!r}.")
    path = files(__package__).joinpath(f"{profile_id}.json")
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"No packaged target profile {profile_id!r}.") from exc
    return target_profile_from_mapping(payload)


def target_profile_from_mapping(raw: Mapping[str, Any]) -> TargetProfile:
    """Validate and parse a JSON-like target profile mapping."""
    schema_version = raw.get("schema_version")
    if schema_version != TARGET_PROFILE_SCHEMA_VERSION:
        raise ValueError(
            "target profile schema_version must be "
            f"{TARGET_PROFILE_SCHEMA_VERSION!r}, got {schema_version!r}."
        )
    _reject_forbidden_value_keys(raw, context="target profile")
    profile_id = _required_string(raw, "profile_id")
    country = _required_string(raw, "country")
    label = _required_string(raw, "label")
    defaults = _required_mapping(raw, "defaults")
    base_period_policy = _required_string(defaults, "base_period_policy")
    default_operation = _required_string(defaults, "operation")
    if default_operation != "sum":
        raise ValueError(
            f"target profile {profile_id!r} must use operation 'sum', "
            f"got {default_operation!r}."
        )
    targets = tuple(
        _target_from_mapping(target)
        for target in _required_mapping_sequence(raw, "targets")
    )
    if not targets:
        raise ValueError(f"target profile {profile_id!r} must declare targets.")
    duplicate_ids = sorted(
        target_id
        for target_id in {target.target_id for target in targets}
        if sum(target.target_id == target_id for target in targets) > 1
    )
    if duplicate_ids:
        raise ValueError(
            f"target profile {profile_id!r} has duplicate target_id(s): "
            f"{duplicate_ids}."
        )
    return TargetProfile(
        profile_id=profile_id,
        country=country,
        label=label,
        base_period_policy=base_period_policy,
        default_operation=default_operation,
        targets=targets,
    )


def _target_from_mapping(raw: Mapping[str, Any]) -> TargetProfileTarget:
    _reject_forbidden_value_keys(raw, context="target profile row")
    target_id = _required_string(raw, "target_id")
    family = _required_string(raw, "family")
    geography_levels = tuple(_required_string_sequence(raw, "geography_levels"))
    if not geography_levels:
        raise ValueError(f"target profile row {target_id!r} needs geography_levels.")
    ledger_selector = _required_mapping(raw, "ledger_selector")
    measurement = _required_mapping(raw, "measurement")
    _reject_forbidden_contract_keys(
        ledger_selector,
        context=f"target profile row {target_id!r} ledger_selector",
    )
    _reject_forbidden_contract_keys(
        measurement,
        context=f"target profile row {target_id!r} measurement",
    )
    bindings_payload = _required_mapping(raw, "bindings")
    bindings = {
        backend: _binding_from_mapping(
            backend,
            payload,
            target_id=target_id,
        )
        for backend, payload in bindings_payload.items()
    }
    if not bindings:
        raise ValueError(f"target profile row {target_id!r} needs bindings.")
    tolerance = raw.get("tolerance")
    if tolerance is not None:
        if not isinstance(tolerance, int | float) or isinstance(tolerance, bool):
            raise ValueError(f"target profile row {target_id!r}: invalid tolerance.")
        tolerance = float(tolerance)
    return TargetProfileTarget(
        target_id=target_id,
        family=family,
        geography_levels=geography_levels,
        ledger_selector=ledger_selector,
        measurement=measurement,
        bindings=bindings,
        tolerance=tolerance,
    )


def _binding_from_mapping(
    backend: str,
    raw: Any,
    *,
    target_id: str,
) -> TargetProfileBinding:
    if not isinstance(backend, str) or not backend:
        raise ValueError(f"target profile row {target_id!r}: bad binding backend.")
    if not isinstance(raw, Mapping):
        raise ValueError(
            f"target profile row {target_id!r}: binding {backend!r} must be an object."
        )
    _reject_forbidden_value_keys(raw, context=f"{backend} binding")
    _reject_forbidden_contract_keys(
        raw,
        context=f"target profile row {target_id!r} {backend} binding",
    )
    metric_name = _required_string(raw, "metric_name")
    return TargetProfileBinding(
        backend=backend,
        metric_name=metric_name,
        payload=dict(raw),
    )


def _reject_forbidden_value_keys(raw: Mapping[str, Any], *, context: str) -> None:
    forbidden = {"aggregation", "operation", "registry", "target_value", "value"}
    present = sorted(key for key in forbidden if key in raw)
    if present:
        raise ValueError(
            f"{context} must not declare {present}; Ledger profiles use implicit "
            "Ledger source selection and sum-only measurement, with values "
            "coming from Ledger facts."
        )


def _reject_forbidden_contract_keys(value: Any, *, context: str) -> None:
    """Reject target-value or registry controls nested in contract payloads.

    Filter thresholds such as ``{"operator": ">", "value": 0}`` are valid
    measurement predicates, so this recursive guard allows ``value`` only in
    recognized filter predicate objects. Other ``value`` keys are rejected so
    target amounts cannot hide inside selectors or measurement contracts.
    """

    if isinstance(value, Mapping):
        forbidden = {"aggregation", "operation", "registry", "target_value"}
        if not _is_filter_predicate(value):
            forbidden = forbidden | {"value"}
        present = sorted(key for key in forbidden if key in value)
        if present:
            raise ValueError(
                f"{context} must not declare {present}; Ledger target profiles "
                "use implicit source selection and sum-only measurement, with "
                "values coming from Ledger facts."
            )
        for key, item in value.items():
            _reject_forbidden_contract_keys(item, context=f"{context}.{key}")
    elif isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _reject_forbidden_contract_keys(item, context=f"{context}[{index}]")


def _is_filter_predicate(value: Mapping[str, Any]) -> bool:
    return (
        "value" in value
        and "operator" in value
        and ("concept" in value or "variable" in value)
    )


def _required_string(raw: Mapping[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"target profile field {key!r} must be a non-empty string.")
    return value


def _required_mapping(raw: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = raw.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"target profile field {key!r} must be an object.")
    return value


def _required_mapping_sequence(
    raw: Mapping[str, Any],
    key: str,
) -> tuple[Mapping[str, Any], ...]:
    value = raw.get(key)
    if not isinstance(value, list | tuple):
        raise ValueError(f"target profile field {key!r} must be a list.")
    rows: list[Mapping[str, Any]] = []
    for index, row in enumerate(value):
        if not isinstance(row, Mapping):
            raise ValueError(
                f"target profile field {key!r} row {index} must be an object."
            )
        rows.append(row)
    return tuple(rows)


def _required_string_sequence(raw: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key)
    if not isinstance(value, list | tuple):
        raise ValueError(f"target profile field {key!r} must be a list.")
    strings: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ValueError(
                f"target profile field {key!r} item {index} must be a non-empty string."
            )
        strings.append(item)
    return tuple(strings)


__all__ = [
    "TARGET_PROFILE_SCHEMA_VERSION",
    "TargetProfile",
    "TargetProfileBinding",
    "TargetProfileTarget",
    "load_target_profile",
    "target_profile_from_mapping",
]
