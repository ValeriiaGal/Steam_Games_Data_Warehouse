"""Unit tests for small helper functions in the load step."""

from datetime import date

import numpy as np
import pandas as pd

from pipeline.load import date_key, to_rows


def test_date_key_is_yyyymmdd():
    assert date_key(date(2026, 11, 18)) == 20261118
    assert date_key(date(2027, 1, 5)) == 20270105


def test_to_rows_turns_missing_values_into_none():
    df = pd.DataFrame({"appid": [1, 2], "developer": ["Valve", np.nan]})
    assert to_rows(df, ["appid", "developer"]) == [(1, "Valve"), (2, None)]