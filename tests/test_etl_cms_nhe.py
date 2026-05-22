"""Tests for CMS National Health Expenditure Account loader."""

from sqlmodel import Session, select

from db.etl_cms_nhe import (
    SOURCE_TABLE,
    available_cms_nhe_years,
    load_cms_nhe_data,
    load_cms_nhe_targets,
)
from db.schema import DataSource, GeographicLevel, Stratum, Target, TargetType, init_db


def test_available_cms_nhe_years_includes_latest_historical_year():
    assert 2024 in available_cms_nhe_years()


def test_load_cms_nhe_data_reads_packaged_medicaid_source():
    data = load_cms_nhe_data()

    assert data["source_url"] == (
        "https://www.cms.gov/files/zip/"
        "national-health-expenditures-type-service-source-funds-cy-1960-2024.zip"
    )
    assert data["medicaid_benefits_by_year"][2024] == 931_692_000_000
    assert data["medicaid_benefits_by_year"][2023] == 873_681_000_000


def test_load_cms_nhe_targets_creates_national_medicaid_benefits(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_cms_nhe_targets(session, years=[2024])
        stratum = session.exec(
            select(Stratum).where(Stratum.stratum_group_id == "cms_nhe_national")
        ).one()
        target = session.exec(
            select(Target).where(
                Target.stratum_id == stratum.id,
                Target.variable == "medicaid_benefits",
                Target.period == 2024,
            )
        ).one()

    assert target.value == 931_692_000_000
    assert target.target_type == TargetType.AMOUNT
    assert target.geographic_level == GeographicLevel.NATIONAL
    assert target.source == DataSource.CMS_MEDICAID
    assert target.source_table == SOURCE_TABLE


def test_load_cms_nhe_targets_is_idempotent(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_cms_nhe_targets(session, years=[2024])
        load_cms_nhe_targets(session, years=[2024])
        targets = session.exec(
            select(Target).where(
                Target.variable == "medicaid_benefits",
                Target.period == 2024,
            )
        ).all()

    assert len(targets) == 1
