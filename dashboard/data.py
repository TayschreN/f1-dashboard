"""Loads every processed parquet table once at app startup and exposes them
as module-level DataFrames. Small enough (a few MB total) to keep fully in
memory rather than querying on every callback."""
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"


def _load(name):
    return pd.read_parquet(DATA_DIR / f"{name}.parquet")


dim_drivers = _load("dim_drivers")
dim_constructors = _load("dim_constructors")
dim_circuits = _load("dim_circuits")
dim_races = _load("dim_races")

fact_results = _load("fact_results")
fact_sprint_results = _load("fact_sprint_results")
fact_qualifying = _load("fact_qualifying")
fact_pitstops = _load("fact_pitstops")
agg_lap_times = _load("agg_lap_times")

driver_standings_progression = _load("driver_standings_progression")
constructor_standings_progression = _load("constructor_standings_progression")
season_champions = _load("season_champions")

agg_driver_career = _load("agg_driver_career")
agg_driver_season = _load("agg_driver_season")
agg_constructor_career = _load("agg_constructor_career")
agg_constructor_season = _load("agg_constructor_season")
agg_circuit_stats = _load("agg_circuit_stats")

MIN_SEASON = int(dim_races["season"].min())
MAX_SEASON = int(dim_races["season"].max())

# Convenience lookups used across several callbacks
DRIVER_OPTIONS = (
    agg_driver_career.sort_values("wins", ascending=False)[["driverId", "fullName"]]
    .rename(columns={"fullName": "label", "driverId": "value"})
    .to_dict("records")
)
CONSTRUCTOR_OPTIONS = (
    agg_constructor_career.sort_values("points", ascending=False)[["constructor_family"]]
    .drop_duplicates()
    .assign(label=lambda d: d["constructor_family"], value=lambda d: d["constructor_family"])
    [["label", "value"]]
    .to_dict("records")
)
CIRCUIT_OPTIONS = (
    agg_circuit_stats.sort_values("races_held", ascending=False)[["circuitId", "circuitName"]]
    .rename(columns={"circuitName": "label", "circuitId": "value"})
    .to_dict("records")
)


def season_filtered(df, season_range, season_col="season"):
    """Filter any table with a season/year column to the selected [min, max] range."""
    lo, hi = season_range
    return df[(df[season_col] >= lo) & (df[season_col] <= hi)]
