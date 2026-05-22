"""Tests for CMS Marketplace OEP state-level PUF loader."""

from sqlmodel import Session, select

from db.etl_cms_aca_oep import (
    available_cms_aca_oep_years,
    load_cms_aca_oep_data,
    load_cms_aca_oep_targets,
)
from db.schema import Stratum, Target, TargetType, init_db


def test_available_cms_aca_oep_years():
    assert available_cms_aca_oep_years() == [2024]


def test_load_cms_aca_oep_data_reads_packaged_2024_source():
    data = load_cms_aca_oep_data(2024)
    ca = data["states"]["CA"]

    assert data["source_url"] == (
        "https://www.cms.gov/files/zip/2024-oep-state-level-public-use-file.zip"
    )
    assert ca["enrollment"] == 1_784_653
    assert ca["aptc_recipients"] == 1_554_271
    assert ca["avg_monthly_aptc"] == 526
    assert ca["annual_aptc_amount"] == 9_810_558_552


def test_load_cms_aca_oep_targets_creates_state_aptc_amount(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_cms_aca_oep_targets(session, years=[2024])
        ca_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA ACA Marketplace")
        ).one()
        target = session.exec(
            select(Target).where(
                Target.stratum_id == ca_stratum.id,
                Target.variable == "aca_aptc_amount",
                Target.period == 2024,
            )
        ).one()

    assert target.value == 9_810_558_552
    assert target.target_type == TargetType.AMOUNT
    assert target.source_table == "2024 OEP State-Level Public Use File"
