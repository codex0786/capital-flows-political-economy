import pandas as pd
import pytest

from src.common import PROCESSED


@pytest.fixture(scope="session")
def annual():
    return pd.read_parquet(PROCESSED / "annual_country_panel.parquet")


@pytest.fixture(scope="session")
def quarterly():
    return pd.read_parquet(PROCESSED / "quarterly_country_panel.parquet")


@pytest.fixture(scope="session")
def meta():
    return pd.read_csv(PROCESSED / "country_metadata.csv")
