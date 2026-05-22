from db.etl_soi import (
    available_soi_table_1_4_years,
    available_soi_years,
    load_soi_table_1_1_data,
    load_soi_table_1_4_data,
    load_soi_targets,
)
from db.schema import Target, TargetType, init_db
from sqlmodel import Session, select


def test_available_soi_years_include_latest_table_1_1_sources():
    assert available_soi_years() == [2020, 2021, 2022, 2023]


def test_load_soi_table_1_1_data_reads_packaged_2023_source():
    data = load_soi_table_1_1_data(2023)

    assert data["source_url"] == "https://www.irs.gov/pub/irs-soi/23in11si.xls"
    assert data["total_returns"] == 160_602_107
    assert data["total_agi"] == 15_286_017_359_000
    assert data["total_income_tax_after_credits_returns"] == 111_545_061
    assert data["total_income_tax"] == 2_147_909_818_000
    assert data["returns_by_agi_bracket"]["100k_to_200k"] == 27_602_755
    assert data["agi_by_bracket"]["100k_to_200k"] == 3_818_295_141_000
    assert (
        data["income_tax_after_credits_returns_by_bracket"]["100k_to_200k"]
        == 27_208_705
    )
    assert data["income_tax_by_bracket"]["100k_to_200k"] == 409_532_689_000


def test_available_soi_years_include_latest_table_1_4_sources():
    assert available_soi_table_1_4_years() == [2021, 2022, 2023]


def test_load_soi_table_1_4_data_reads_packaged_2023_wage_source():
    data = load_soi_table_1_4_data(2023)
    income_sources = data["income_sources"]

    assert data["source_url"] == "https://www.irs.gov/pub/irs-soi/23in14ar.xls"
    assert data["total_employment_income_returns"] == 128_591_050
    assert data["total_employment_income"] == 10_204_095_705_000
    assert data["employment_income_returns_by_agi_bracket"]["100k_to_200k"] == 23_193_910
    assert data["employment_income_by_agi_bracket"]["100k_to_200k"] == 2_774_550_975_000
    assert income_sources["wages_salaries"]["total_returns"] == 128_591_050
    assert income_sources["wages_salaries"]["total_amount"] == 10_204_095_705_000
    assert income_sources["net_capital_gains"]["total_returns"] == 12_392_020
    assert income_sources["net_capital_gains"]["total_amount"] == 966_168_014_000
    assert income_sources["taxable_ira_distributions"]["total_returns"] == 16_694_154
    assert income_sources["taxable_ira_distributions"]["total_amount"] == 438_147_938_000
    assert income_sources["taxable_pension_income"]["total_returns"] == 29_541_284
    assert income_sources["taxable_pension_income"]["total_amount"] == 932_130_236_000
    assert income_sources["unemployment_compensation"]["total_returns"] == 4_697_502
    assert income_sources["unemployment_compensation"]["total_amount"] == 30_939_046_000
    assert income_sources["taxable_social_security"]["total_returns"] == 25_716_763
    assert income_sources["taxable_social_security"]["total_amount"] == 527_072_873_000


def test_load_soi_table_1_4_data_handles_2021_column_layout():
    data = load_soi_table_1_4_data(2021)
    income_sources = data["income_sources"]

    assert income_sources["net_capital_gains"]["total_amount"] == 2_048_795_356_000
    assert income_sources["taxable_ira_distributions"]["total_amount"] == 408_382_461_000
    assert income_sources["taxable_pension_income"]["total_amount"] == 858_038_339_000
    assert income_sources["unemployment_compensation"]["total_amount"] == 208_872_354_000
    assert income_sources["taxable_social_security"]["total_amount"] == 412_830_233_000


def test_load_soi_targets_writes_table_1_4_source_variables(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_targets(session, years=[2023])
        target = session.exec(
            select(Target).where(
                Target.variable == "taxable_pension_income_amount",
                Target.target_type == TargetType.AMOUNT,
                Target.period == 2023,
                Target.source_table == "Table 1.4",
                Target.value == 932_130_236_000,
            )
        ).one()

    assert target.value == 932_130_236_000


def test_load_soi_targets_writes_income_tax_liability_returns(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_targets(session, years=[2023])
        target = session.exec(
            select(Target).where(
                Target.variable == "income_tax_liability_returns",
                Target.target_type == TargetType.COUNT,
                Target.period == 2023,
                Target.source_table == "Table 1.1",
                Target.value == 111_545_061,
            )
        ).one()

    assert target.value == 111_545_061


def test_load_soi_targets_is_idempotent_for_table_1_1_and_1_4(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_targets(session, years=[2023])
        load_soi_targets(session, years=[2023])
        targets = session.exec(
            select(Target).where(
                Target.variable == "income_tax_liability_returns",
                Target.target_type == TargetType.COUNT,
                Target.period == 2023,
                Target.source_table == "Table 1.1",
            )
        ).all()

    assert len(targets) == 20
