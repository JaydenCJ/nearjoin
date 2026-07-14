"""Table I/O: CSV reading, column extraction, output shaping, JSON export."""

import io
import json

import pytest

from nearjoin.errors import ColumnNotFoundError, EmptyInputError
from nearjoin.joiner import join_values
from nearjoin.tabular import (
    column_values,
    matched_rows,
    read_rows,
    result_to_json,
    rows_to_csv_text,
    unmatched_table,
)


def rows_from(text: str):
    return read_rows(io.StringIO(text), source="test.csv")


def test_read_rows_parses_header_and_data():
    rows = rows_from("id,name\n1,Acme\n2,Zenith\n")
    assert rows == [{"id": "1", "name": "Acme"}, {"id": "2", "name": "Zenith"}]


def test_read_rows_rejects_empty_file_and_header_only():
    with pytest.raises(EmptyInputError):
        rows_from("")
    with pytest.raises(EmptyInputError):
        rows_from("id,name\n")


def test_column_values_missing_column_names_the_alternatives():
    rows = rows_from("id,name\n1,Acme\n")
    with pytest.raises(ColumnNotFoundError) as excinfo:
        column_values(rows, "company", source="test.csv")
    assert "'company'" in str(excinfo.value)
    assert "'name'" in str(excinfo.value)


def test_column_values_turns_missing_cells_into_empty_strings():
    rows = rows_from("id,name\n1,Acme\n2\n")
    assert column_values(rows, "name") == ["Acme", ""]


def test_matched_rows_prefix_columns_and_carry_score():
    left = rows_from("id,name\nL1,Acme Inc\n")
    right = rows_from("acct,customer\nR1,ACME Corp\n")
    result = join_values(["Acme Inc"], ["ACME Corp"], kind="name")
    out = matched_rows(result, left, right)
    assert out[0]["left_id"] == "L1"
    assert out[0]["right_acct"] == "R1"
    assert out[0]["match_score"] == "100"
    assert out[0]["match_verdict"] == "match"
    assert "match_explanation" in out[0]
    bare = matched_rows(result, left, right, include_explanation=False)
    assert "match_explanation" not in bare[0]


def test_rows_to_csv_text_unions_headers_in_first_seen_order():
    text = rows_to_csv_text([{"a": "1", "b": "2"}, {"a": "3", "c": "4"}])
    lines = text.strip().split("\n")
    assert lines[0] == "a,b,c"
    assert lines[1] == "1,2,"
    assert lines[2] == "3,,4"


def test_result_to_json_is_valid_and_complete():
    left = rows_from("id,name\nL1,Acme Inc\nL2,Solo Left\n")
    right = rows_from("acct,customer\nR1,ACME Corp\n")
    result = join_values(["Acme Inc", "Solo Left"], ["ACME Corp"], kind="name")
    payload = json.loads(result_to_json(result, left, right))
    assert payload["kind"] == "name"
    assert len(payload["matches"]) == 1
    assert payload["matches"][0]["explanation"]["score"] == 100.0
    assert payload["unmatched_left"] == [{"id": "L2", "name": "Solo Left"}]
    assert payload["unmatched_right"] == []
    assert payload["blocking"]["pairs_possible"] == 2


def test_unmatched_table_selects_rows_by_index():
    rows = rows_from("id,name\n1,A\n2,B\n3,C\n")
    assert unmatched_table(rows, (0, 2)) == [
        {"id": "1", "name": "A"},
        {"id": "3", "name": "C"},
    ]
