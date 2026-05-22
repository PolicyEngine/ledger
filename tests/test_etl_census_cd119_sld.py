"""Tests for Census CD119 state-legislative district source rows."""

from db.etl_census_cd119_sld import (
    available_census_cd119_sld_years,
    census_cd119_sld_source_url,
    load_census_cd119_sld_rows,
)


def test_available_census_cd119_sld_years():
    assert available_census_cd119_sld_years() == [2024]


def test_load_census_cd119_sld_rows_reads_packaged_california_artifact():
    rows = load_census_cd119_sld_rows(2024)
    rows_by_geo_stat = {(row["GEO_ID"], row["source_column_id"]): row for row in rows}
    upper_geos = {
        row["GEO_ID"]
        for row in rows
        if row["statistic"] == "person_count"
        and row["geography_level"] == "state_legislative_district_upper"
    }
    lower_geos = {
        row["GEO_ID"]
        for row in rows
        if row["statistic"] == "person_count"
        and row["geography_level"] == "state_legislative_district_lower"
    }

    assert census_cd119_sld_source_url(2024).endswith(
        "/119th-congressional-district-summary-file/"
    )
    assert len(rows) == 13_686
    assert len(upper_geos) == 1_964
    assert len(lower_geos) == 4_879

    ca_sd_1_population = rows_by_geo_stat[("610U900US06001", "P0010001")]
    ca_sd_1_households = rows_by_geo_stat[("610U900US06001", "H0030002")]
    ca_ad_80_population = rows_by_geo_stat[("620L900US06080", "P0010001")]
    ca_ad_80_households = rows_by_geo_stat[("620L900US06080", "H0030002")]

    assert ca_sd_1_population["NAME"] == "State Senate District 1"
    assert ca_sd_1_population["geography_level"] == ("state_legislative_district_upper")
    assert ca_sd_1_population["state_name"] == "California"
    assert ca_sd_1_population["source_zip_url"].endswith("/California/ca2020.cd19.zip")
    assert ca_sd_1_population["value"] == 943_108
    assert ca_sd_1_population["source_data_row_number"] == 12_850
    assert ca_sd_1_households["value"] == 361_548

    assert ca_ad_80_population["NAME"] == "Assembly District 80"
    assert ca_ad_80_population["geography_level"] == (
        "state_legislative_district_lower"
    )
    assert ca_ad_80_population["value"] == 515_699
    assert ca_ad_80_households["value"] == 154_291
