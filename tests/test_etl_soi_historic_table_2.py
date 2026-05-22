"""Tests for IRS SOI Historic Table 2 source-backed loader."""

from sqlmodel import Session, select

from db.etl_soi_historic_table_2 import (
    available_soi_historic_table_2_years,
    load_soi_historic_table_2_data,
    load_soi_historic_table_2_targets,
)
from db.schema import Stratum, Target, TargetType, init_db


def test_available_soi_historic_table_2_years():
    assert available_soi_historic_table_2_years() == [2020, 2021, 2022]


def test_load_soi_historic_table_2_data_reads_packaged_2022_source():
    data = load_soi_historic_table_2_data(2022)
    ca = data["states"]["CA"]
    national = data["national"]

    assert data["source_url"] == "https://www.irs.gov/pub/irs-soi/22in55cmcsv.csv"
    assert data["national_positive_agi_returns"] == 156_997_270
    assert data["state_positive_agi_returns"]["CA"] == 18_149_050
    assert data["national_individual_count_by_agi"]["1_to_10k"] == 16_745_140
    assert data["state_individual_count_by_agi"]["CA"]["1_to_10k"] == 1_930_150
    assert national["income_tax_before_credits"]["returns"] == 128_597_410
    assert national["income_tax_before_credits"]["amount"] == 2_253_465_308_000
    assert ca["tax_unit_count"]["returns"] == 18_487_690
    assert ca["adjusted_gross_income"]["amount"] == 1_987_000_701_000
    assert ca["income_tax_before_credits"]["returns"] == 15_196_040
    assert ca["income_tax_before_credits"]["amount"] == 330_995_863_000
    assert ca["income_tax_liability"]["returns"] == 13_527_790
    assert ca["income_tax_liability"]["amount"] == 312_788_705_000
    assert national["tax_filer_individual_count"]["returns"] == 293_617_150
    assert ca["tax_filer_individual_count"]["returns"] == 34_443_160
    assert national["premium_tax_credit"]["returns"] == 7_841_370
    assert national["premium_tax_credit"]["amount"] == 53_910_175_000
    assert national["advance_premium_tax_credit"]["returns"] == 8_540_300
    assert national["advance_premium_tax_credit"]["amount"] == 60_737_303_000
    assert ca["premium_tax_credit"]["returns"] == 988_090
    assert ca["premium_tax_credit"]["amount"] == 6_379_623_000
    assert ca["advance_premium_tax_credit"]["returns"] == 1_115_830
    assert ca["advance_premium_tax_credit"]["amount"] == 7_383_222_000
    assert national["eitc"]["returns"] == 23_692_190
    assert national["eitc"]["amount"] == 59_204_588_000
    assert ca["eitc"]["returns"] == 2_519_120
    assert ca["eitc"]["amount"] == 5_770_703_000
    assert national["real_estate_taxes"]["returns"] == 12_905_140
    assert national["real_estate_taxes"]["amount"] == 106_195_956_000
    assert national["limited_state_local_taxes"]["returns"] == 14_968_720
    assert national["limited_state_local_taxes"]["amount"] == 122_622_124_000
    assert national["mortgage_interest_paid"]["returns"] == 11_485_760
    assert national["mortgage_interest_paid"]["amount"] == 141_959_142_000
    assert national["home_mortgage_personal_seller"]["returns"] == 282_610
    assert national["home_mortgage_personal_seller"]["amount"] == 2_791_432_000
    assert national["deductible_points"]["returns"] == 755_210
    assert national["deductible_points"]["amount"] == 1_105_711_000
    assert national["investment_interest_paid"]["returns"] == 829_750
    assert national["investment_interest_paid"]["amount"] == 23_338_421_000
    assert national["interest_paid_deduction"]["amount"] == 169_194_706_000
    assert ca["real_estate_taxes"]["returns"] == 2_492_940
    assert ca["real_estate_taxes"]["amount"] == 25_031_551_000
    assert ca["limited_state_local_taxes"]["returns"] == 2_831_790
    assert ca["limited_state_local_taxes"]["amount"] == 25_187_253_000
    assert ca["mortgage_interest_paid"]["returns"] == 2_327_780
    assert ca["mortgage_interest_paid"]["amount"] == 35_409_552_000
    assert ca["home_mortgage_personal_seller"]["returns"] == 74_940
    assert ca["home_mortgage_personal_seller"]["amount"] == 796_174_000
    assert ca["deductible_points"]["returns"] == 242_960
    assert ca["deductible_points"]["amount"] == 365_291_000
    assert ca["investment_interest_paid"]["returns"] == 166_720
    assert ca["investment_interest_paid"]["amount"] == 4_351_598_000
    assert ca["interest_paid_deduction"]["amount"] == 40_922_615_000
    assert ca["wages_salaries"]["returns"] == 14_835_020
    assert ca["wages_salaries"]["amount"] == 1_351_712_860_000
    assert ca["net_capital_gains"]["returns"] == 3_852_470
    assert ca["net_capital_gains"]["amount"] == 177_049_871_000
    assert ca["taxable_ira_distributions"]["returns"] == 1_524_670
    assert ca["taxable_ira_distributions"]["amount"] == 45_827_203_000
    assert ca["taxable_pension_income"]["returns"] == 2_809_820
    assert ca["taxable_pension_income"]["amount"] == 104_443_330_000
    assert ca["unemployment_compensation"]["returns"] == 1_047_530
    assert ca["unemployment_compensation"]["amount"] == 6_879_591_000
    assert ca["taxable_social_security"]["returns"] == 2_351_720
    assert ca["taxable_social_security"]["amount"] == 45_572_185_000
    assert data["national_eitc_by_child_count"]["0_children"]["returns"] == 6_717_560
    assert (
        data["national_eitc_by_child_count"]["0_children"]["amount"]
        == 2_449_267_000
    )
    assert data["national_eitc_by_child_count"]["3plus_children"]["returns"] == 3_080_790
    assert (
        data["national_eitc_by_child_count"]["3plus_children"]["amount"]
        == 13_861_484_000
    )
    assert (
        data["national_eitc_by_agi_and_child_count"]["1_to_10k"]["1_child"][
            "returns"
        ]
        == 936_920
    )
    assert (
        data["national_eitc_by_agi_and_child_count"]["1_to_10k"]["1_child"][
            "amount"
        ]
        == 1_976_997_000
    )
    assert (
        data["states_eitc_by_child_count"]["CA"]["2_children"]["amount"]
        == 2_096_996_000
    )


def test_load_soi_historic_table_2_targets_creates_state_source_variables(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_historic_table_2_targets(session, years=[2022])
        ca_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA All Filers")
        ).one()
        target = session.exec(
            select(Target).where(
                Target.stratum_id == ca_stratum.id,
                Target.variable == "taxable_social_security_amount",
                Target.period == 2022,
            )
        ).one()

    assert target.value == 45_572_185_000
    assert target.target_type == TargetType.AMOUNT
    assert target.source_table == "Historic Table 2"
    assert target.source_url == "https://www.irs.gov/pub/irs-soi/22in55cmcsv.csv"


def test_load_soi_historic_table_2_targets_creates_tax_variables(tmp_path):
    engine = init_db(tmp_path / "targets.db")

    with Session(engine) as session:
        load_soi_historic_table_2_targets(session, years=[2022])
        ca_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA All Filers")
        ).one()
        national_stratum = session.exec(
            select(Stratum).where(Stratum.name == "US All Filers")
        ).one()
        ca_target = session.exec(
            select(Target).where(
                Target.stratum_id == ca_stratum.id,
                Target.variable == "real_estate_taxes_amount",
                Target.period == 2022,
            )
        ).one()
        national_target = session.exec(
            select(Target).where(
                Target.stratum_id == national_stratum.id,
                Target.variable == "income_tax_before_credits_returns",
                Target.period == 2022,
            )
        ).one()
        national_salt_target = session.exec(
            select(Target).where(
                Target.stratum_id == national_stratum.id,
                Target.variable == "limited_state_local_taxes_amount",
                Target.period == 2022,
            )
        ).one()
        national_interest_target = session.exec(
            select(Target).where(
                Target.stratum_id == national_stratum.id,
                Target.variable == "interest_paid_deduction_amount",
                Target.period == 2022,
            )
        ).one()
        ca_aca_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA All Filers")
        ).one()
        ca_aca_target = session.exec(
            select(Target).where(
                Target.stratum_id == ca_aca_stratum.id,
                Target.variable == "aca_ptc_returns",
                Target.period == 2022,
            )
        ).one()
        national_eitc_child_stratum = session.exec(
            select(Stratum).where(Stratum.name == "US EITC 3+ children")
        ).one()
        national_eitc_child_target = session.exec(
            select(Target).where(
                Target.stratum_id == national_eitc_child_stratum.id,
                Target.variable == "eitc_amount",
                Target.period == 2022,
            )
        ).one()
        ca_eitc_child_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA EITC 2 children")
        ).one()
        ca_eitc_child_target = session.exec(
            select(Target).where(
                Target.stratum_id == ca_eitc_child_stratum.id,
                Target.variable == "eitc_claims",
                Target.period == 2022,
            )
        ).one()
        national_eitc_agi_child_stratum = session.exec(
            select(Stratum).where(
                Stratum.name == "US AGI 1_to_10k EITC 1 child"
            )
        ).one()
        national_eitc_agi_child_target = session.exec(
            select(Target).where(
                Target.stratum_id == national_eitc_agi_child_stratum.id,
                Target.variable == "eitc_amount",
                Target.period == 2022,
            )
        ).one()
        ca_agi_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA AGI 1_to_10k")
        ).one()
        ca_agi_person_target = session.exec(
            select(Target).where(
                Target.stratum_id == ca_agi_stratum.id,
                Target.variable == "tax_filer_individual_count",
                Target.period == 2022,
            )
        ).one()
        positive_agi_stratum = session.exec(
            select(Stratum).where(Stratum.name == "CA Filers with Positive AGI")
        ).one()
        positive_agi_target = session.exec(
            select(Target).where(
                Target.stratum_id == positive_agi_stratum.id,
                Target.variable == "tax_unit_count",
                Target.period == 2022,
            )
        ).one()

    assert ca_target.value == 25_031_551_000
    assert ca_target.target_type == TargetType.AMOUNT
    assert national_target.value == 128_597_410
    assert national_target.target_type == TargetType.COUNT
    assert national_salt_target.value == 122_622_124_000
    assert national_salt_target.target_type == TargetType.AMOUNT
    assert national_interest_target.value == 169_194_706_000
    assert national_interest_target.target_type == TargetType.AMOUNT
    assert national_interest_target.notes
    assert "Schedule A lines 8a, 8b, 8c, and 9" in national_interest_target.notes
    assert ca_aca_target.value == 988_090
    assert ca_aca_target.target_type == TargetType.COUNT
    assert national_eitc_child_target.value == 13_861_484_000
    assert national_eitc_child_target.target_type == TargetType.AMOUNT
    assert national_eitc_child_target.notes
    assert "3+ EITC child-count category" in national_eitc_child_target.notes
    assert ca_eitc_child_target.value == 550_910
    assert ca_eitc_child_target.target_type == TargetType.COUNT
    assert national_eitc_agi_child_target.value == 1_976_997_000
    assert national_eitc_agi_child_target.target_type == TargetType.AMOUNT
    assert ca_agi_person_target.value == 1_930_150
    assert ca_agi_person_target.target_type == TargetType.COUNT
    assert ca_agi_person_target.notes
    assert "do not represent the full U.S. population" in ca_agi_person_target.notes
    assert positive_agi_target.value == 18_149_050
    assert positive_agi_target.target_type == TargetType.COUNT
