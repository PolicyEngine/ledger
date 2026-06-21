from __future__ import annotations

import pytest

from policyengine_ledger.target_profiles import (
    TARGET_PROFILE_SCHEMA_VERSION,
    load_target_profile,
    target_profile_from_mapping,
)


def test__given_uk_local_profile__then_it_declares_measurement_contracts() -> None:
    # When
    profile = load_target_profile("uk_local_geography")

    # Then
    assert profile.country == "uk"
    assert profile.default_operation == "sum"
    assert profile.base_period_policy == "latest_not_after_build_base_period"

    constituency_metrics = [
        target.binding("policyengine").metric_name
        for target in profile.targets_for_geography("constituency")
    ]
    assert constituency_metrics[:4] == [
        "hmrc/self_employment_income/amount",
        "hmrc/self_employment_income/count",
        "hmrc/employment_income/amount",
        "hmrc/employment_income/count",
    ]
    assert "uc_hh_3plus_children" in constituency_metrics
    assert "rent/private_rent" not in constituency_metrics

    local_authority_metrics = [
        target.binding("policyengine").metric_name
        for target in profile.targets_for_geography("local_authority")
    ]
    assert "uc_households" in local_authority_metrics
    assert "ons/equiv_net_income_bhc" in local_authority_metrics
    assert "rent/private_rent" in local_authority_metrics
    assert "uc_hh_0_children" not in local_authority_metrics


def test__given_count_like_profile_rows__then_they_are_still_sum_measurements() -> None:
    # When
    profile = load_target_profile("uk_local_geography")
    employment_count = next(
        target
        for target in profile.targets
        if target.target_id == "hmrc.employment_income.count"
    )

    # Then
    assert profile.default_operation == "sum"
    assert employment_count.measurement["concept"] == "uk.person.count"
    assert employment_count.binding("policyengine").payload["value_variable"] == (
        "person_count"
    )


@pytest.mark.parametrize("forbidden", ["registry", "aggregation", "target_value"])
def test__given_forbidden_profile_option__then_profile_is_rejected(
    forbidden: str,
) -> None:
    # Given
    payload = {
        "schema_version": TARGET_PROFILE_SCHEMA_VERSION,
        "profile_id": "bad",
        "country": "uk",
        "label": "Bad profile",
        "defaults": {
            "base_period_policy": "latest_not_after_build_base_period",
            "operation": "sum",
        },
        "targets": [
            {
                "target_id": "bad.target",
                "family": "bad",
                "geography_levels": ["country"],
                "ledger_selector": {"source_name": "bad"},
                "measurement": {"entity": "household", "concept": "bad"},
                "bindings": {
                    "policyengine": {
                        "metric_name": "bad",
                        forbidden: "not allowed",
                    }
                },
            }
        ],
    }

    # When / Then
    with pytest.raises(ValueError, match=forbidden):
        target_profile_from_mapping(payload)


@pytest.mark.parametrize(
    ("container", "forbidden"),
    [
        ("ledger_selector", "value"),
        ("ledger_selector", "target_value"),
        ("measurement", "value"),
        ("measurement", "aggregation"),
        ("measurement", "registry"),
    ],
)
def test__given_nested_forbidden_profile_option__then_profile_is_rejected(
    container: str,
    forbidden: str,
) -> None:
    # Given
    payload = _minimal_profile_payload()
    payload["targets"][0][container][forbidden] = "not allowed"

    # When / Then
    with pytest.raises(ValueError, match=forbidden):
        target_profile_from_mapping(payload)


def test__given_filter_threshold_values__then_profile_is_allowed() -> None:
    # Given
    payload = _minimal_profile_payload()
    payload["targets"][0]["measurement"]["filters"] = [
        {"concept": "uk.tax.income_tax", "operator": ">", "value": 0}
    ]

    # When
    profile = target_profile_from_mapping(payload)

    # Then
    assert profile.targets[0].measurement["filters"][0]["value"] == 0


def test__given_non_sum_default_operation__then_profile_is_rejected() -> None:
    # Given
    payload = {
        "schema_version": TARGET_PROFILE_SCHEMA_VERSION,
        "profile_id": "bad",
        "country": "uk",
        "label": "Bad profile",
        "defaults": {
            "base_period_policy": "latest_not_after_build_base_period",
            "operation": "count",
        },
        "targets": [],
    }

    # When / Then
    with pytest.raises(ValueError, match="operation 'sum'"):
        target_profile_from_mapping(payload)


def _minimal_profile_payload() -> dict[str, object]:
    return {
        "schema_version": TARGET_PROFILE_SCHEMA_VERSION,
        "profile_id": "test_profile",
        "country": "uk",
        "label": "Test profile",
        "defaults": {
            "base_period_policy": "latest_not_after_build_base_period",
            "operation": "sum",
        },
        "targets": [
            {
                "target_id": "test.target",
                "family": "test",
                "geography_levels": ["country"],
                "ledger_selector": {"source_name": "test"},
                "measurement": {"entity": "household", "concept": "test"},
                "bindings": {
                    "policyengine": {
                        "metric_name": "test",
                    }
                },
            }
        ],
    }
