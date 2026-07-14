"""CLI behavior end to end, driven in-process through cli.main()."""

import csv
import io
import json

import pytest

from nearjoin import __version__
from nearjoin.cli import main


def run(capsys, *argv):
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip() == f"nearjoin {__version__}"


def test_join_examples_produces_expected_matches(capsys, crm_csv, billing_csv):
    code, out, err = run(
        capsys, "join", str(crm_csv), str(billing_csv),
        "--left-on", "name", "--right-on", "customer", "--kind", "name",
    )
    assert code == 0
    rows = list(csv.DictReader(io.StringIO(out)))
    verdicts = {row["left_name"]: row["match_verdict"] for row in rows}
    assert verdicts["Acme, Inc."] == "match"
    assert verdicts["Northwind Traders"] == "review"
    # Unmatched rows are not in the match output.
    assert "Ironclad Security" not in verdicts
    assert "matched 9, review 1" in err


def test_join_auto_detects_address_kind(capsys, crm_csv, billing_csv):
    code, out, err = run(
        capsys, "join", str(crm_csv), str(billing_csv),
        "--left-on", "address", "--right-on", "street_address",
    )
    assert code == 0
    assert "kind=address" in err
    rows = list(csv.DictReader(io.StringIO(out)))
    # The house-number drift 45 vs 47 must not be silently matched.
    assert all(row["left_address"] != "45 Elm Avenue" for row in rows)


def test_join_quiet_suppresses_summary(capsys, crm_csv, billing_csv):
    code, out, err = run(
        capsys, "join", str(crm_csv), str(billing_csv),
        "--left-on", "name", "--right-on", "customer", "--quiet",
    )
    assert code == 0
    assert err == ""


def test_join_writes_output_and_unmatched_files(capsys, tmp_path, crm_csv, billing_csv):
    out_file = tmp_path / "matched.csv"
    left_file = tmp_path / "left_only.csv"
    right_file = tmp_path / "right_only.csv"
    code, out, _ = run(
        capsys, "join", str(crm_csv), str(billing_csv),
        "--left-on", "name", "--right-on", "customer", "--quiet",
        "-o", str(out_file),
        "--unmatched-left", str(left_file),
        "--unmatched-right", str(right_file),
    )
    assert code == 0
    assert out == ""  # everything went to files
    matched = list(csv.DictReader(out_file.open()))
    assert len(matched) == 10
    left_only = list(csv.DictReader(left_file.open()))
    assert {row["name"] for row in left_only} == {
        "Ironclad Security", "Sunrise Dental Group",
    }
    right_only = list(csv.DictReader(right_file.open()))
    assert {row["customer"] for row in right_only} == {"Kings Cross Hardware"}


def test_unmatched_file_keeps_header_when_every_row_matches(capsys, tmp_path, write_csv):
    # An empty leftover set must still yield a valid CSV with a header, so a
    # downstream `csv.DictReader` (or a spreadsheet) opens it without fuss.
    left = write_csv("id,name", "1,Acme Inc")
    right = write_csv("id,name", "9,ACME Corporation")
    right_file = tmp_path / "right_only.csv"
    code, _, _ = run(
        capsys, "join", str(left), str(right), "--left-on", "name", "--quiet",
        "--unmatched-right", str(right_file),
    )
    assert code == 0
    reader = csv.DictReader(right_file.open())
    assert reader.fieldnames == ["id", "name"]
    assert list(reader) == []


def test_join_json_format_includes_explanations(capsys, crm_csv, billing_csv):
    code, out, _ = run(
        capsys, "join", str(crm_csv), str(billing_csv),
        "--left-on", "name", "--right-on", "customer", "--quiet",
        "--format", "json",
    )
    assert code == 0
    payload = json.loads(out)
    first = payload["matches"][0]
    assert first["explanation"]["left"]["raw"] == "Acme, Inc."
    assert first["explanation"]["left"]["steps"]


def test_join_no_explain_drops_the_column(capsys, crm_csv, billing_csv):
    code, out, _ = run(
        capsys, "join", str(crm_csv), str(billing_csv),
        "--left-on", "name", "--right-on", "customer", "--quiet", "--no-explain",
    )
    assert code == 0
    header = out.splitlines()[0]
    assert "match_explanation" not in header
    assert "match_score" in header


def test_join_threshold_flags_are_honored(capsys, crm_csv, billing_csv):
    # Raising review above Northwind's 77.6 drops it from the output entirely.
    code, out, _ = run(
        capsys, "join", str(crm_csv), str(billing_csv),
        "--left-on", "name", "--right-on", "customer", "--quiet",
        "--review", "80",
    )
    assert code == 0
    assert "Northwind" not in out


def test_join_missing_column_is_a_clean_error(capsys, crm_csv, billing_csv):
    code, out, err = run(
        capsys, "join", str(crm_csv), str(billing_csv), "--left-on", "company",
    )
    assert code == 2
    assert "nearjoin: error:" in err
    assert "'company' not found" in err


def test_join_missing_file_is_a_clean_error(capsys, crm_csv):
    code, _, err = run(
        capsys, "join", str(crm_csv), "no_such_file.csv", "--left-on", "name",
    )
    assert code == 2
    assert "no such file" in err


def test_join_bad_thresholds_are_a_clean_error(capsys, crm_csv, billing_csv):
    code, _, err = run(
        capsys, "join", str(crm_csv), str(billing_csv),
        "--left-on", "name", "--right-on", "customer",
        "--threshold", "60", "--review", "90",
    )
    assert code == 2
    assert "review" in err


def test_score_command_prints_long_explanation(capsys):
    code, out, _ = run(capsys, "score", "Acme, Inc.", "ACME Corporation")
    assert code == 0
    assert out.startswith("score 100 / 100")
    assert "dropped legal suffix 'inc'" in out


def test_score_command_json_output(capsys):
    code, out, _ = run(
        capsys, "score", "123 Main St", "125 Main St", "--kind", "address", "--json",
    )
    assert code == 0
    payload = json.loads(out)
    assert payload["penalties"][0]["name"] == "numeric_mismatch"
    assert payload["score"] < 70.0


def test_keys_command_shows_trace_and_keys(capsys):
    code, out, _ = run(capsys, "keys", "The Hilltop Bakery Inc.")
    assert code == 0
    assert "normalized: 'hilltop bakery'" in out
    assert "p4:hill" in out
    assert "init:bh" in out


def test_keys_command_empty_value_says_so(capsys):
    code, out, _ = run(capsys, "keys", "  ")
    assert code == 0
    assert "can never match" in out


def test_empty_input_file_is_a_clean_error(capsys, tmp_path, billing_csv):
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    code, _, err = run(
        capsys, "join", str(empty), str(billing_csv), "--left-on", "name",
    )
    assert code == 2
    assert "no header row" in err
