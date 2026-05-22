"""Tests for persisted source-file ingestion."""

from __future__ import annotations

import json
import sqlite3
import zipfile
from types import SimpleNamespace

from sqlmodel import Session, select

from db.cli import cmd_source_manifest
from db.pe_source_inventory import pe_source_manifest_rows, pe_source_specs
from db.pe_source_inventory import UK_TARGET_URL_FILES
from db.schema import (
    Jurisdiction,
    SourceArtifact,
    SourceRow,
    SourceTable,
    get_engine,
    init_db,
)
from db import source_files
from db.source_files import SourceArtifactSpec, ingest_source_artifact


def test_ingest_csv_source_artifact(tmp_path):
    source_path = tmp_path / "sample.csv"
    source_path.write_text("state,value\nCA,1\nNY,2\n", encoding="utf-8")
    db_path = tmp_path / "sources.db"
    init_db(db_path)

    spec = SourceArtifactSpec(
        slug="test/sample",
        path=source_path,
        origin_project="policyengine-us-data",
        pipeline="database",
        jurisdiction=Jurisdiction.US,
        source_id="test-source",
    )

    with Session(get_engine(db_path)) as session:
        result = ingest_source_artifact(session, spec)
        session.commit()
        artifact = session.exec(select(SourceArtifact)).one()
        table = session.exec(select(SourceTable)).one()
        rows = session.exec(select(SourceRow).order_by(SourceRow.row_number)).all()

    assert result.row_count == 2
    assert artifact.sha256
    assert table.column_count == 2
    assert json.loads(rows[0].values_json) == {"state": "CA", "value": "1"}


def test_ingest_zip_source_artifact(tmp_path):
    source_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(source_path, "w") as archive:
        archive.writestr("nested/data.csv", "name,count\nalpha,3\n")
    db_path = tmp_path / "sources.db"
    init_db(db_path)

    spec = SourceArtifactSpec(
        slug="test/bundle",
        path=source_path,
        origin_project="policyengine-us-data",
        pipeline="database",
        jurisdiction=Jurisdiction.US,
        source_id="test-source",
    )

    with Session(get_engine(db_path)) as session:
        result = ingest_source_artifact(session, spec)
        session.commit()
        table = session.exec(select(SourceTable)).one()
        row = session.exec(select(SourceRow)).one()

    assert result.table_count == 1
    assert "nested/data.csv" in table.name
    assert json.loads(row.values_json) == {"name": "alpha", "count": "3"}


def test_ingest_url_source_artifact(tmp_path, monkeypatch):
    def fake_fetch_url(_url):
        return b"name,count\nalpha,3\n", "text/csv", "https://example.test/source.csv"

    monkeypatch.setattr(source_files, "_fetch_url", fake_fetch_url)
    db_path = tmp_path / "sources.db"
    init_db(db_path)

    spec = SourceArtifactSpec(
        slug="test/url",
        source_url="https://example.test/source.csv",
        filename="source.csv",
        origin_project="policyengine-uk-data",
        pipeline="target-registry-live-sources",
        jurisdiction=Jurisdiction.UK,
        source_id="test-source",
    )

    with Session(get_engine(db_path)) as session:
        result = ingest_source_artifact(session, spec)
        session.commit()
        artifact = session.exec(select(SourceArtifact)).one()
        row = session.exec(select(SourceRow)).one()

    assert result.row_count == 1
    assert artifact.local_path is None
    assert artifact.source_url == "https://example.test/source.csv"
    assert json.loads(row.values_json) == {"name": "alpha", "count": "3"}


def test_ingest_url_source_artifact_records_fetch_error(tmp_path, monkeypatch):
    def fake_fetch_url(_url):
        raise RuntimeError("blocked")

    monkeypatch.setattr(source_files, "_fetch_url", fake_fetch_url)
    db_path = tmp_path / "sources.db"
    init_db(db_path)

    spec = SourceArtifactSpec(
        slug="test/url-error",
        source_url="https://example.test/source.html",
        filename="source.html",
        origin_project="policyengine-uk-data",
        pipeline="target-registry-live-sources",
        jurisdiction=Jurisdiction.UK,
        source_id="test-source",
    )

    with Session(get_engine(db_path)) as session:
        result = ingest_source_artifact(session, spec)
        session.commit()
        artifact = session.exec(select(SourceArtifact)).one()
        rows = session.exec(select(SourceRow).order_by(SourceRow.row_number)).all()

    lines = "\n".join(json.loads(row.values_json)["line"] for row in rows)
    assert result.row_count == 5
    assert artifact.content_type == "text/plain"
    assert artifact.source_url == "https://example.test/source.html"
    assert "RuntimeError" in lines


def test_ingest_pdf_source_artifact(tmp_path):
    source_path = tmp_path / "source.pdf"
    content = b"%PDF-1.4\nsource bytes\n%%EOF"
    source_path.write_bytes(content)
    db_path = tmp_path / "sources.db"
    init_db(db_path)

    spec = SourceArtifactSpec(
        slug="test/pdf",
        path=source_path,
        origin_project="policyengine-uk-data",
        pipeline="target-registry-live-sources",
        jurisdiction=Jurisdiction.UK,
        source_id="test-source",
    )

    with Session(get_engine(db_path)) as session:
        result = ingest_source_artifact(session, spec)
        session.commit()
        row = session.exec(select(SourceRow)).one()

    payload = json.loads(row.values_json)
    assert result.row_count == 1
    assert payload["filename"] == "source.pdf"
    assert payload["size_bytes"] == len(content)
    assert payload["content_base64"]


def test_pe_source_inventory_finds_both_pipeline_roots(tmp_path):
    pe_us = tmp_path / "policyengine-us-data"
    raw_inputs = pe_us / "policyengine_us_data" / "storage" / "calibration" / "raw_inputs"
    target_inputs = (
        pe_us / "policyengine_us_data" / "storage" / "calibration_targets"
    )
    raw_inputs.mkdir(parents=True)
    target_inputs.mkdir(parents=True)
    (raw_inputs / "irs_soi_sample.csv").write_text("x\n1\n", encoding="utf-8")
    (target_inputs / "snap_state.csv").write_text("x\n1\n", encoding="utf-8")

    specs = pe_source_specs(pe_us_root=pe_us, include_uk=False)

    local_specs = [
        spec for spec in specs if spec.path is not None and spec.path.exists()
    ]

    assert [spec.pipeline for spec in local_specs] == [
        "database",
        "legacy-loss-targets",
    ]
    assert {spec.source_id for spec in local_specs} == {"irs-soi", "usda-snap"}


def test_pe_us_inventory_emits_expected_rows_without_checkout(tmp_path):
    pe_us = tmp_path / "missing-policyengine-us-data"

    specs = pe_source_specs(pe_us_root=pe_us, include_uk=False)
    artifacts = {spec.path.name for spec in specs if spec.path is not None}
    urls = {spec.source_url for spec in specs}

    assert "soi_targets.csv" in artifacts
    assert "block_cd_distributions.csv.gz" in artifacts
    assert "SSPopJul_TR2024.csv" in artifacts
    assert "https://www.irs.gov/pub/irs-soi/23in14ar.xls" in urls
    assert (
        "https://www2.census.gov/programs-surveys/decennial/rdo/"
        "mapping-files/2025/119-congressional-district-befs/cd119.zip"
    ) in urls


def test_pe_source_manifest_marks_expected_missing_files_not_loaded(tmp_path):
    pe_us = tmp_path / "missing-policyengine-us-data"
    specs = pe_source_specs(pe_us_root=pe_us, include_uk=False)

    rows = pe_source_manifest_rows(
        specs,
        arch_db_path=tmp_path / "missing-arch.db",
        pe_us_root=pe_us,
    )

    soi_row = next(
        row for row in rows if row["artifact"].endswith("soi_targets.csv")
    )
    assert soi_row["status"] == "todo"
    assert soi_row["exists_locally"] == "no"
    assert soi_row["arch_source_status"] == "not_loaded"
    assert soi_row["source_cell_status"] == "blocked_by_artifact_status"
    assert soi_row["target_construction_status"] == "not_ready"


def test_pe_us_inventory_can_skip_missing_local_files_for_ingestion(tmp_path):
    pe_us = tmp_path / "missing-policyengine-us-data"

    specs = pe_source_specs(
        pe_us_root=pe_us,
        include_uk=False,
        include_missing_local=False,
    )

    assert all(spec.path is None or spec.path.exists() for spec in specs)
    assert "https://www.irs.gov/pub/irs-soi/23in14ar.xls" in {
        spec.source_url for spec in specs
    }


def test_pe_us_inventory_includes_publisher_source_documents(tmp_path):
    pe_us = tmp_path / "policyengine-us-data"
    (pe_us / "policyengine_us_data" / "storage").mkdir(parents=True)

    specs = pe_source_specs(pe_us_root=pe_us, include_uk=False)
    urls = {spec.source_url for spec in specs}
    filenames = {spec.filename for spec in specs if spec.filename}

    assert "https://www.irs.gov/pub/irs-soi/23in14ar.xls" in urls
    assert "irs_soi_ty2023_table_1_4.xls" in filenames
    assert "https://www.irs.gov/pub/irs-soi/23in25ic.xls" in urls
    assert "irs_soi_ty2023_table_2_5.xls" in filenames
    assert "usda_snap_fy69_to_current.zip" in filenames
    assert "jct_2024_tax_expenditure_report.html" in filenames
    assert (
        "https://www2.census.gov/programs-surveys/decennial/rdo/"
        "mapping-files/2019/116-congressional-district-bef/cd116.zip"
    ) in urls
    assert (
        "https://www2.census.gov/programs-surveys/decennial/rdo/"
        "mapping-files/2025/119-congressional-district-befs/cd119.zip"
    ) in urls
    assert "census_2020_pl_94_171_ca.zip" in filenames
    assert "census_2020_pl_94_171_dc.zip" in filenames
    assert "census_2020_baf_ca.zip" in filenames
    assert "census_2020_baf_dc.zip" in filenames
    assert "https://fred.stlouisfed.org/series/BOGZ1FL192090005Q" in urls
    assert (
        "https://liheappm.acf.gov/sites/default/files/private/congress/"
        "profiles/2024/FY2024_AllStates%28National%29_Profile.pdf"
    ) in urls
    assert (
        "https://ohss.dhs.gov/sites/default/files/2024-06/"
        "2024_0418_ohss_estimates-of-the-unauthorized-immigrant-population-"
        "residing-in-the-united-states-january-2018%25E2%2580%2593january-2022.pdf"
    ) in urls
    assert "cbo_2026_02_budget_projections.xlsx" in filenames
    assert "cbo_2026_02_snap_baseline.xlsx" in filenames
    assert "treasury_tax_expenditures_fy2023.pdf" in filenames
    assert "cms_2025_medicare_trustees_report.pdf" in filenames
    assert "vanguard_how_america_saves_2024.pdf" in filenames


def test_pe_source_manifest_rows_mark_unloaded_artifacts(tmp_path):
    pe_us = tmp_path / "policyengine-us-data"
    storage = pe_us / "policyengine_us_data" / "storage"
    targets = storage / "calibration_targets"
    targets.mkdir(parents=True)
    (targets / "soi_targets.csv").write_text("x\n1\n", encoding="utf-8")

    specs = pe_source_specs(pe_us_root=pe_us, include_uk=False)
    rows = pe_source_manifest_rows(
        specs,
        arch_db_path=tmp_path / "missing.db",
        pe_us_root=pe_us,
    )

    soi_row = next(row for row in rows if row["artifact"] == "policyengine_us_data/storage/calibration_targets/soi_targets.csv")
    assert soi_row["status"] == "todo"
    assert soi_row["arch_source_status"] == "not_loaded"
    assert soi_row["source_cell_status"] == "blocked_by_artifact_status"
    assert soi_row["target_construction_status"] == "not_ready"
    assert soi_row["exists_locally"] == "yes"
    assert "including values PE omits" in soi_row["value_capture_policy"]


def test_pe_source_manifest_rows_surface_arch_inventory_error(tmp_path):
    db_path = tmp_path / "old-schema.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE unrelated (id INTEGER)")

    spec = SourceArtifactSpec(
        slug="policyengine-us-data/test/source",
        source_url="https://example.test/source.csv",
        filename="source.csv",
        origin_project="policyengine-us-data",
        pipeline="soi-source-pages",
        jurisdiction=Jurisdiction.US,
        source_id="irs-soi",
    )

    [row] = pe_source_manifest_rows(
        [spec],
        arch_db_path=db_path,
        pe_us_root=tmp_path / "policyengine-us-data",
    )

    assert row["status"] == "todo"
    assert row["arch_source_status"] == "inventory_error"
    assert row["source_cell_status"] == "blocked_by_artifact_status"
    assert row["target_construction_status"] == "not_ready"


def test_pe_source_manifest_rows_require_parsed_artifact(tmp_path, monkeypatch):
    def fake_fetch_url(_url):
        raise RuntimeError("blocked")

    monkeypatch.setattr(source_files, "_fetch_url", fake_fetch_url)
    db_path = tmp_path / "sources.db"
    init_db(db_path)
    spec = SourceArtifactSpec(
        slug="policyengine-us-data/irs/fetch-error",
        source_url="https://example.test/source.html",
        filename="source.html",
        origin_project="policyengine-us-data",
        pipeline="soi-source-pages",
        jurisdiction=Jurisdiction.US,
        source_id="irs-soi",
    )

    with Session(get_engine(db_path)) as session:
        ingest_source_artifact(session, spec)
        session.commit()

    [row] = pe_source_manifest_rows(
        [spec],
        arch_db_path=db_path,
        pe_us_root=tmp_path / "policyengine-us-data",
    )

    assert row["status"] == "todo"
    assert row["arch_source_status"] == "fetch_error"
    assert row["source_cell_status"] == "blocked_by_artifact_status"
    assert row["target_construction_status"] == "not_ready"
    assert row["artifact_role"] == "publisher_source"


def test_pe_source_manifest_rows_mark_parsed_no_rows_not_done(tmp_path):
    source_path = tmp_path / "empty.csv"
    source_path.write_text("x\n", encoding="utf-8")
    db_path = tmp_path / "sources.db"
    init_db(db_path)
    spec = SourceArtifactSpec(
        slug="policyengine-us-data/test/empty",
        path=source_path,
        origin_project="policyengine-us-data",
        pipeline="legacy-loss-targets",
        jurisdiction=Jurisdiction.US,
        source_id="irs-soi",
    )

    with Session(get_engine(db_path)) as session:
        ingest_source_artifact(session, spec)
        session.commit()

    [row] = pe_source_manifest_rows(
        [spec],
        arch_db_path=db_path,
        pe_us_root=tmp_path / "policyengine-us-data",
    )

    assert row["status"] == "todo"
    assert row["arch_source_status"] == "parsed_no_rows"
    assert row["source_cell_status"] == "blocked_by_artifact_status"
    assert row["target_construction_status"] == "not_ready"


def test_pe_source_manifest_rows_fetch_error_replaces_prior_success(
    tmp_path,
    monkeypatch,
):
    source_url = "https://example.test/source.csv"
    db_path = tmp_path / "sources.db"
    init_db(db_path)
    spec = SourceArtifactSpec(
        slug="policyengine-us-data/test/url",
        source_url=source_url,
        filename="source.csv",
        origin_project="policyengine-us-data",
        pipeline="soi-source-pages",
        jurisdiction=Jurisdiction.US,
        source_id="irs-soi",
    )

    def fake_fetch_url(_url):
        return b"x\n1\n", "text/csv", source_url

    monkeypatch.setattr(source_files, "_fetch_url", fake_fetch_url)
    with Session(get_engine(db_path)) as session:
        ingest_source_artifact(session, spec)
        session.commit()

    def fake_fetch_error(_url):
        raise RuntimeError("blocked")

    monkeypatch.setattr(source_files, "_fetch_url", fake_fetch_error)
    with Session(get_engine(db_path)) as session:
        ingest_source_artifact(session, spec)
        session.commit()

    [row] = pe_source_manifest_rows(
        [spec],
        arch_db_path=db_path,
        pe_us_root=tmp_path / "policyengine-us-data",
    )

    assert row["status"] == "todo"
    assert row["arch_source_status"] == "fetch_error"
    assert row["source_cell_status"] == "blocked_by_artifact_status"


def test_pe_source_manifest_rows_reject_identity_mismatch(tmp_path, monkeypatch):
    def fake_fetch_url(_url):
        return b"x\n1\n", "text/csv", "https://example.test/old-source.csv"

    monkeypatch.setattr(source_files, "_fetch_url", fake_fetch_url)
    db_path = tmp_path / "sources.db"
    init_db(db_path)
    loaded_spec = SourceArtifactSpec(
        slug="policyengine-us-data/test/source",
        source_url="https://example.test/old-source.csv",
        filename="source.csv",
        origin_project="policyengine-us-data",
        pipeline="soi-source-pages",
        jurisdiction=Jurisdiction.US,
        source_id="irs-soi",
    )
    expected_spec = SourceArtifactSpec(
        slug=loaded_spec.slug,
        source_url="https://example.test/new-source.csv",
        filename="source.csv",
        origin_project="policyengine-us-data",
        pipeline="soi-source-pages",
        jurisdiction=Jurisdiction.US,
        source_id="irs-soi",
    )

    with Session(get_engine(db_path)) as session:
        ingest_source_artifact(session, loaded_spec)
        session.commit()

    [row] = pe_source_manifest_rows(
        [expected_spec],
        arch_db_path=db_path,
        pe_us_root=tmp_path / "policyengine-us-data",
    )

    assert row["status"] == "todo"
    assert row["arch_source_status"] == "identity_mismatch"
    assert row["source_cell_status"] == "blocked_by_artifact_status"


def test_pe_source_manifest_rows_mark_parsed_artifact_done(tmp_path):
    source_path = tmp_path / "source.csv"
    source_path.write_text("x\n1\n", encoding="utf-8")
    db_path = tmp_path / "sources.db"
    init_db(db_path)
    spec = SourceArtifactSpec(
        slug="policyengine-us-data/test/source",
        path=source_path,
        origin_project="policyengine-us-data",
        pipeline="legacy-loss-targets",
        jurisdiction=Jurisdiction.US,
        source_id="irs-soi",
    )

    with Session(get_engine(db_path)) as session:
        ingest_source_artifact(session, spec)
        session.commit()

    [row] = pe_source_manifest_rows(
        [spec],
        arch_db_path=db_path,
        pe_us_root=tmp_path / "policyengine-us-data",
    )

    assert row["status"] == "done"
    assert row["arch_source_status"] == "row_parsed"
    assert row["source_cell_status"] == "not_started"
    assert row["target_construction_status"] == "not_ready"
    assert row["artifact_role"] == "pe_intermediate"


def test_source_manifest_cli_defaults_to_jurisdiction_paths(tmp_path, monkeypatch):
    pe_us = tmp_path / "policyengine-us-data"
    targets = pe_us / "policyengine_us_data" / "storage" / "calibration_targets"
    targets.mkdir(parents=True)
    (targets / "soi_targets.csv").write_text("x\n1\n", encoding="utf-8")
    db_path = tmp_path / "sources.db"
    init_db(db_path)
    monkeypatch.chdir(tmp_path)

    cmd_source_manifest(
        SimpleNamespace(
            db=str(db_path),
            inventory="pe",
            jurisdiction="us",
            pe_us_root=str(pe_us),
            pe_uk_root=str(tmp_path / "missing-policyengine-uk-data"),
            output=None,
            markdown=None,
        )
    )

    assert (tmp_path / "docs/pe-us-source-manifest.csv").exists()
    assert (tmp_path / "docs/pe-us-source-manifest.md").exists()
    assert not (tmp_path / "docs/pe-source-manifest.csv").exists()


def test_pe_source_inventory_includes_long_term_ssa_inputs(tmp_path):
    pe_us = tmp_path / "policyengine-us-data"
    storage = pe_us / "policyengine_us_data" / "storage"
    long_term = storage / "long_term_target_sources"
    long_term.mkdir(parents=True)
    (long_term / "sources.json").write_text("{}", encoding="utf-8")
    (long_term / "trustees_2025_current_law.csv").write_text(
        "year,value\n2025,1\n", encoding="utf-8"
    )
    (storage / "SSPopJul_TR2024.csv").write_text(
        "Year,Age,Total\n2025,0,1\n", encoding="utf-8"
    )
    (storage / "social_security_aux.csv").write_text(
        "year,value\n2025,1\n", encoding="utf-8"
    )

    specs = pe_source_specs(pe_us_root=pe_us, include_uk=False)
    slugs = {spec.slug for spec in specs}

    assert any("sspopjul_tr2024.csv" in slug for slug in slugs)
    assert any("social_security_aux.csv" in slug for slug in slugs)
    assert any(spec.pipeline == "long-term-target-references" for spec in specs)


def test_pe_uk_inventory_includes_registry_config_and_reference_pages(tmp_path):
    pe_uk = tmp_path / "policyengine-uk-data"
    targets = pe_uk / "policyengine_uk_data" / "targets"
    targets.mkdir(parents=True)
    (targets / "sources.yaml").write_text("dwp: {}\n", encoding="utf-8")

    specs = pe_source_specs(pe_uk_root=pe_uk, include_us=False)
    pipelines = {spec.pipeline for spec in specs}
    filenames = {spec.filename for spec in specs if spec.filename}

    assert "target-registry-config" in pipelines
    assert "target-registry-live-sources" in pipelines
    assert len(filenames) >= len(UK_TARGET_URL_FILES)
    assert "dwp_stat_xplore.html" in filenames
    assert "uk_government_2025_spp_review.pdf" in filenames
