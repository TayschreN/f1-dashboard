"""
ETL pipeline: raw Formula 1 CSVs -> clean, enriched analytical tables.

Layers (medallion-style, pandas instead of Spark since the volume here -
~600k rows at most - doesn't justify distributed compute):
  RAW        data/raw/*.csv                  original source data (Ergast-schema
                                              export, seasons 1950-2024)
  PROCESSED  data/processed/*.parquet        cleaned, joined, feature-engineered
                                              tables consumed by the notebook and
                                              the Dash app

Run:
    python etl/build_processed_data.py
"""
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def time_to_seconds(t):
    """Convert 'M:SS.mmm' or 'H:MM:SS.mmm' lap/qualifying time strings to float seconds."""
    if pd.isna(t):
        return np.nan
    t = str(t).strip()
    if t == "" or t.lower() in ("nan", "none"):
        return np.nan
    parts = t.split(":")
    try:
        parts = [float(p) for p in parts]
    except ValueError:
        return np.nan
    if len(parts) == 3:
        h, m, s = parts
        return h * 3600 + m * 60 + s
    if len(parts) == 2:
        m, s = parts
        return m * 60 + s
    if len(parts) == 1:
        return parts[0]
    return np.nan


def strip_accents(s):
    """ASCII-fold a string (Räikkönen -> Raikkonen) for easier text search/filtering."""
    if pd.isna(s):
        return s
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)
    )


# Status -> category mapping. Built from the 137 distinct status strings in
# status.csv. "Finished" and "+N Lap(s)" mean the car was running/classified
# at the end; everything else is a non-finish of some kind.
_MECHANICAL_KEYWORDS = [
    "engine", "gearbox", "transmission", "electrical", "brakes", "clutch",
    "hydraulics", "suspension", "turbo", "fuel", "ignition", "oil", "throttle",
    "differential", "tyre", "wheel", "steering", "radiator", "power unit",
    "water", "exhaust", "mechanical", "driveshaft", "axle", "battery",
    "electronics", "vibrations", "spark plugs", "supercharger", "ers",
    "undertray", "pneumatics", "track rod", "crankshaft", "cv joint", "wing",
    "chassis", "magneto", "alternator", "distributor", "injection",
    "heat shield", "cooling system", "brake duct", "seat", "damage",
    "drivetrain", "launch control", "refuelling", "stalled", "puncture",
]
_ACCIDENT_KEYWORDS = [
    "accident", "collision", "spun off", "injury", "injured", "illness",
    "unwell", "eye injury", "safety belt", "safety", "debris",
    "not restarted", "fatal",
]
_EXCLUDED_KEYWORDS = [
    "did not qualify", "did not prequalify", "disqualified", "excluded",
    "107%", "underweight", "withdrew", "not classified",
]


def categorize_status(status: str) -> str:
    if pd.isna(status):
        return "Other"
    s = status.lower()
    if s == "finished" or re.match(r"^\+\d+ laps?$", s):
        return "Finished"
    if any(k in s for k in _ACCIDENT_KEYWORDS):
        return "Accident"
    if any(k in s for k in _EXCLUDED_KEYWORDS):
        return "Excluded/DNQ"
    if any(k in s for k in _MECHANICAL_KEYWORDS):
        return "Mechanical"
    return "Other"


def is_classified(status: str) -> bool:
    """True if the car finished the race running (Finished or lapped-but-running)."""
    if pd.isna(status):
        return False
    s = status.lower()
    return s == "finished" or bool(re.match(r"^\+\d+ laps?$", s))


def constructor_family(name: str) -> str:
    """
    Collapse chassis+engine constructor variants (e.g. 'Cooper-Climax',
    'Cooper-Maserati') into one team family ('Cooper'). This dataset follows
    classic Ergast conventions where pre-1980s entries are sometimes split by
    engine supplier even though only one constructor championship is awarded
    per season.
    """
    if pd.isna(name):
        return name
    return str(name).split("-")[0].strip()


# --------------------------------------------------------------------------- #
# Hand-verified season champions (season -> driver / constructor).
# Sourced from ESPN's official all-time F1 champions list (Dec 2025) and
# cross-checked against Wikipedia's "List of Formula One World Drivers'
# Champions". This table exists because championships are NOT always the
# driver/team with the most *combined* points in this results file:
#   - scoring rules changed repeatedly (best-4-of-Y, best-5-of-Y drop
#     scores etc. were used through the late 1980s/early 1990s)
#   - 1964 (Surtees) and 1988 (Senna) were won by the driver with FEWER
#     total points than the runner-up, under the rules of those seasons
#   - 1997 Schumacher was stripped of his points/standing after the season
# Rather than re-implement 70+ years of scoring-rule history (and risk
# getting a famous year wrong), the champion of record is hardcoded here;
# everything else in this pipeline (wins, podiums, poles, points-in-season)
# is computed directly from the results data.
# --------------------------------------------------------------------------- #
SEASON_CHAMPIONS = {
    # season: (driverId, constructor_family)   constructor_family is None pre-1958
    1950: ("farina", None), 1951: ("fangio", None), 1952: ("ascari", None),
    1953: ("ascari", None), 1954: ("fangio", None), 1955: ("fangio", None),
    1956: ("fangio", None), 1957: ("fangio", None),
    1958: ("hawthorn", "Vanwall"), 1959: ("jack_brabham", "Cooper"),
    1960: ("jack_brabham", "Cooper"), 1961: ("phil_hill", "Ferrari"),
    1962: ("hill", "BRM"), 1963: ("clark", "Lotus"), 1964: ("surtees", "Ferrari"),
    1965: ("clark", "Lotus"), 1966: ("jack_brabham", "Brabham"),
    1967: ("hulme", "Brabham"), 1968: ("hill", "Lotus"),
    1969: ("stewart", "Matra"), 1970: ("rindt", "Lotus"),
    1971: ("stewart", "Tyrrell"), 1972: ("emerson_fittipaldi", "Lotus"),
    1973: ("stewart", "Lotus"), 1974: ("emerson_fittipaldi", "McLaren"),
    1975: ("lauda", "Ferrari"), 1976: ("hunt", "Ferrari"),
    1977: ("lauda", "Ferrari"), 1978: ("mario_andretti", "Lotus"),
    1979: ("scheckter", "Ferrari"), 1980: ("jones", "Williams"),
    1981: ("piquet", "Williams"), 1982: ("keke_rosberg", "Ferrari"),
    1983: ("piquet", "Ferrari"), 1984: ("lauda", "McLaren"),
    1985: ("prost", "McLaren"), 1986: ("prost", "Williams"),
    1987: ("piquet", "Williams"), 1988: ("senna", "McLaren"),
    1989: ("prost", "McLaren"), 1990: ("senna", "McLaren"),
    1991: ("senna", "McLaren"), 1992: ("mansell", "Williams"),
    1993: ("prost", "Williams"), 1994: ("michael_schumacher", "Williams"),
    1995: ("michael_schumacher", "Benetton"), 1996: ("damon_hill", "Williams"),
    1997: ("villeneuve", "Williams"), 1998: ("hakkinen", "McLaren"),
    1999: ("hakkinen", "Ferrari"), 2000: ("michael_schumacher", "Ferrari"),
    2001: ("michael_schumacher", "Ferrari"), 2002: ("michael_schumacher", "Ferrari"),
    2003: ("michael_schumacher", "Ferrari"), 2004: ("michael_schumacher", "Ferrari"),
    2005: ("alonso", "Renault"), 2006: ("alonso", "Renault"),
    2007: ("raikkonen", "Ferrari"), 2008: ("hamilton", "Ferrari"),
    2009: ("button", "Brawn"), 2010: ("vettel", "Red Bull"),
    2011: ("vettel", "Red Bull"), 2012: ("vettel", "Red Bull"),
    2013: ("vettel", "Red Bull"), 2014: ("hamilton", "Mercedes"),
    2015: ("hamilton", "Mercedes"), 2016: ("rosberg", "Mercedes"),
    2017: ("hamilton", "Mercedes"), 2018: ("hamilton", "Mercedes"),
    2019: ("hamilton", "Mercedes"), 2020: ("hamilton", "Mercedes"),
    2021: ("max_verstappen", "Mercedes"), 2022: ("max_verstappen", "Red Bull"),
    2023: ("max_verstappen", "Red Bull"), 2024: ("max_verstappen", "McLaren"),
}
# NOTE: constructor family in the dict above is the DRIVER champion's team
# except where noted; the actual constructors' title in 2021 went to Mercedes
# even though Verstappen (Red Bull) won the drivers' title that year - a good
# reminder these are two separate championships. Fixed explicitly below.
SEASON_CHAMPIONS[2021] = ("max_verstappen", "Mercedes")  # constructors' title: Mercedes


def main():
    print("Loading raw CSVs...")
    drivers = pd.read_csv(RAW_DIR / "drivers.csv")
    constructors = pd.read_csv(RAW_DIR / "constructors.csv")
    circuits = pd.read_csv(RAW_DIR / "circuits.csv")
    races = pd.read_csv(RAW_DIR / "races.csv")
    results = pd.read_csv(RAW_DIR / "race_results.csv")
    qualifying = pd.read_csv(RAW_DIR / "qualifying_results.csv")
    sprint = pd.read_csv(RAW_DIR / "sprint_results.csv")
    pitstops = pd.read_csv(RAW_DIR / "pitstops.csv")
    lap_times = pd.read_csv(RAW_DIR / "lap_times.csv")
    status = pd.read_csv(RAW_DIR / "status.csv")

    # ----------------------------------------------------------------- #
    # Dimensions
    # ----------------------------------------------------------------- #
    print("Building dimension tables...")
    drivers["fullName"] = drivers["givenName"] + " " + drivers["familyName"]
    drivers["fullName_ascii"] = drivers["fullName"].apply(strip_accents)
    dim_drivers = drivers[[
        "driverId", "fullName", "givenName", "familyName", "code",
        "permanentNumber", "dateOfBirth", "nationality", "fullName_ascii",
    ]].copy()
    dim_drivers["dateOfBirth"] = pd.to_datetime(dim_drivers["dateOfBirth"], errors="coerce")

    constructors["constructor_family"] = constructors["constructorName"].apply(constructor_family)
    dim_constructors = constructors[[
        "constructorId", "constructorName", "constructor_family", "nationality",
    ]].copy()

    circuits = circuits.rename(columns={"country": "circuitCountry"})
    dim_circuits = circuits[[
        "circuitId", "circuitName", "lat", "long", "locality", "circuitCountry",
    ]].copy()

    races = races.merge(
        circuits[["circuitId", "circuitCountry"]], on="circuitId", how="left"
    )
    races["date"] = pd.to_datetime(races["date"], errors="coerce")
    races["decade"] = (races["season"] // 10) * 10
    races["is_sprint_weekend"] = races["sprint"].notna()
    races["raceId"] = races["season"].astype(str) + "_" + races["round"].astype(str).str.zfill(2)
    dim_races = races[[
        "raceId", "season", "round", "raceName", "circuitId", "circuitName",
        "circuitCountry", "date", "decade", "is_sprint_weekend",
    ]].copy()

    # ----------------------------------------------------------------- #
    # Fact: race results (the core table)
    # ----------------------------------------------------------------- #
    print("Building fact_results...")
    results["raceId"] = results["season"].astype(str) + "_" + results["round"].astype(str).str.zfill(2)
    results = results.merge(
        dim_races[["raceId", "date", "decade", "circuitCountry", "is_sprint_weekend"]],
        on="raceId", how="left",
    )
    results = results.merge(
        dim_drivers[["driverId", "fullName", "nationality"]].rename(
            columns={"fullName": "driverFullName", "nationality": "driverNationality"}
        ),
        on="driverId", how="left",
    )
    results = results.merge(
        dim_constructors[["constructorId", "constructor_family", "nationality"]].rename(
            columns={"nationality": "constructorNationality"}
        ),
        on="constructorId", how="left",
    )
    results["status_category"] = results["status"].apply(categorize_status)
    results["classified"] = results["status"].apply(is_classified)
    results["is_win"] = results["position"] == 1
    results["is_podium"] = results["position"] <= 3
    results["is_top10"] = results["position"] <= 10
    results["points_finish"] = results["points"] > 0
    # grid == 0 means started from pit lane in Ergast convention; treat as NaN for gain calc
    grid_valid = results["grid"].replace(0, np.nan)
    results["position_gained"] = grid_valid - results["position"]
    results["fastestLapTime_sec"] = results["fastestLapTime"].apply(time_to_seconds)

    # IMPORTANT: sprint races (2021+) award their own championship points on
    # top of the main Grand Prix, but live in sprint_results.csv, not
    # race_results.csv. Left out, 2021-2024 points totals silently undercount
    # (e.g. Verstappen's 2021 title-winning total is 7 points short without
    # them). Fold sprint points in here as an explicit extra column so
    # "points" (race only) and "total_points" (race + sprint) are both
    # available and clearly distinguished downstream.
    sprint_points = (
        sprint.groupby(["season", "round", "driverId"])["points"].sum().rename("sprint_points")
    )
    results = results.merge(sprint_points, on=["season", "round", "driverId"], how="left")
    results["sprint_points"] = results["sprint_points"].fillna(0)
    results["total_points"] = results["points"] + results["sprint_points"]

    fact_results = results[[
        "raceId", "season", "round", "decade", "date", "circuitCountry",
        "driverId", "driverFullName", "driverNationality",
        "constructorId", "constructorName", "constructor_family", "constructorNationality",
        "grid", "position", "positionText", "points", "sprint_points", "total_points",
        "laps", "status", "status_category",
        "classified", "is_win", "is_podium", "is_top10", "points_finish",
        "position_gained", "fastestLapRank", "fastestLap_lap", "fastestLapTime_sec",
        "is_sprint_weekend",
    ]].copy()

    # Standalone sprint results table (2021+) for anyone who wants to look at
    # sprint-specific stats (sprint winners, sprint vs. race pace, etc.)
    sprint = sprint.copy()
    sprint["raceId"] = sprint["season"].astype(str) + "_" + sprint["round"].astype(str).str.zfill(2)
    sprint = sprint.merge(
        dim_drivers[["driverId", "fullName"]].rename(columns={"fullName": "driverFullName"}),
        on="driverId", how="left",
    )
    sprint = sprint.merge(
        dim_constructors[["constructorId", "constructor_family"]], on="constructorId", how="left"
    )
    fact_sprint_results = sprint[[
        "raceId", "season", "round", "driverId", "driverFullName",
        "constructorId", "constructor_family", "grid", "position", "points", "laps", "status",
    ]].copy()

    # ----------------------------------------------------------------- #
    # Fact: qualifying
    # ----------------------------------------------------------------- #
    print("Building fact_qualifying...")
    qualifying["raceId"] = qualifying["season"].astype(str) + "_" + qualifying["round"].astype(str).str.zfill(2)
    for col in ["Q1", "Q2", "Q3"]:
        qualifying[col + "_sec"] = qualifying[col].apply(time_to_seconds)
    qualifying["best_time_sec"] = qualifying[["Q1_sec", "Q2_sec", "Q3_sec"]].min(axis=1)
    qualifying = qualifying.merge(
        dim_races[["raceId", "decade"]], on="raceId", how="left"
    )
    fact_qualifying = qualifying[[
        "raceId", "season", "round", "decade", "driverId", "driverName",
        "constructorId", "constructorName", "position",
        "Q1_sec", "Q2_sec", "Q3_sec", "best_time_sec",
    ]].copy()

    # ----------------------------------------------------------------- #
    # Fact: pit stops
    # ----------------------------------------------------------------- #
    print("Building fact_pitstops...")
    pitstops["raceId"] = pitstops["season"].astype(str) + "_" + pitstops["round"].astype(str).str.zfill(2)
    pitstops["duration_sec"] = pd.to_numeric(pitstops["duration"], errors="coerce")
    fact_pitstops = pitstops[["raceId", "season", "round", "driverId", "lap", "stop", "duration_sec"]].copy()
    # Drop implausible outliers (red flags / stop-go penalties recorded as pit stops
    # can be 60s+; keep a generous but sane upper bound for "typical" stop analysis)
    fact_pitstops = fact_pitstops[fact_pitstops["duration_sec"].between(1, 300) | fact_pitstops["duration_sec"].isna()]

    # ----------------------------------------------------------------- #
    # Fact: lap times (+ pre-aggregated version for fast dashboard use)
    # ----------------------------------------------------------------- #
    print("Building fact_lap_times (this table is large, ~590k rows)...")
    lap_times["raceId"] = lap_times["season"].astype(str) + "_" + lap_times["round"].astype(str).str.zfill(2)
    lap_times["time_sec"] = lap_times["time"].apply(time_to_seconds)
    fact_lap_times = lap_times[["raceId", "season", "round", "lapNumber", "driverId", "position", "time_sec"]].copy()

    agg_lap_times = (
        fact_lap_times.groupby(["raceId", "season", "round", "driverId"])
        .agg(avg_lap_sec=("time_sec", "mean"), min_lap_sec=("time_sec", "min"),
             laps_recorded=("time_sec", "count"))
        .reset_index()
    )

    # ----------------------------------------------------------------- #
    # Standings progression (cumulative points/wins within each season)
    # ----------------------------------------------------------------- #
    print("Building standings progression...")
    d_prog = (
        fact_results.sort_values(["season", "round"])
        .groupby(["season", "driverId"])
        .apply(lambda g: g.assign(
            points_cum=g["total_points"].cumsum(),
            wins_cum=g["is_win"].cumsum(),
        ), include_groups=False)
        .reset_index()
    )
    d_prog = d_prog.merge(dim_drivers[["driverId", "fullName"]], on="driverId", how="left")
    d_prog["rank_in_standings"] = d_prog.groupby(["season", "round"])["points_cum"] \
        .rank(method="min", ascending=False)
    driver_standings_progression = d_prog[[
        "season", "round", "driverId", "fullName", "total_points", "points_cum", "wins_cum", "rank_in_standings",
    ]].rename(columns={"fullName": "driverFullName", "total_points": "points"})

    c_prog = (
        fact_results.groupby(["season", "round", "constructor_family"], as_index=False)["total_points"].sum()
        .sort_values(["season", "round"])
        .rename(columns={"total_points": "points"})
    )
    c_prog["points_cum"] = c_prog.groupby(["season", "constructor_family"])["points"].cumsum()
    c_prog["rank_in_standings"] = c_prog.groupby(["season", "round"])["points_cum"] \
        .rank(method="min", ascending=False)
    constructor_standings_progression = c_prog

    # ----------------------------------------------------------------- #
    # Season champions (hand-verified table + points cross-check)
    # ----------------------------------------------------------------- #
    print("Building season_champions...")
    champ_rows = []
    for season, (driver_id, constructor_fam) in SEASON_CHAMPIONS.items():
        driver_name = dim_drivers.loc[dim_drivers["driverId"] == driver_id, "fullName"]
        driver_name = driver_name.iloc[0] if len(driver_name) else driver_id
        champ_rows.append({
            "season": season,
            "champion_driverId": driver_id,
            "champion_driver_name": driver_name,
            "champion_constructor_family": constructor_fam,
        })
    season_champions = pd.DataFrame(champ_rows)

    # ----------------------------------------------------------------- #
    # Aggregates: driver / constructor career & season stats
    # ----------------------------------------------------------------- #
    print("Building driver & constructor aggregates...")
    driver_champ_counts = season_champions["champion_driverId"].value_counts().rename("championships")
    constructor_champ_counts = (
        season_champions.dropna(subset=["champion_constructor_family"])["champion_constructor_family"]
        .value_counts().rename("championships")
    )

    agg_driver_career = (
        fact_results.groupby("driverId")
        .agg(
            races=("raceId", "nunique"),
            wins=("is_win", "sum"),
            podiums=("is_podium", "sum"),
            top10s=("is_top10", "sum"),
            points=("total_points", "sum"),
            dnfs=("classified", lambda s: (~s).sum()),
            first_season=("season", "min"),
            last_season=("season", "max"),
        )
        .reset_index()
    )
    poles = fact_qualifying[fact_qualifying["position"] == 1].groupby("driverId").size().rename("poles")
    agg_driver_career = agg_driver_career.merge(poles, on="driverId", how="left")
    agg_driver_career["poles"] = agg_driver_career["poles"].fillna(0).astype(int)
    agg_driver_career["dnf_rate"] = (agg_driver_career["dnfs"] / agg_driver_career["races"]).round(3)
    agg_driver_career["seasons_active"] = agg_driver_career["last_season"] - agg_driver_career["first_season"] + 1
    agg_driver_career = agg_driver_career.merge(dim_drivers, on="driverId", how="left")
    agg_driver_career = agg_driver_career.merge(driver_champ_counts, left_on="driverId", right_index=True, how="left")
    agg_driver_career["championships"] = agg_driver_career["championships"].fillna(0).astype(int)

    agg_driver_season = (
        fact_results.groupby(["season", "driverId", "driverFullName"])
        .agg(
            races=("raceId", "nunique"), wins=("is_win", "sum"), podiums=("is_podium", "sum"),
            points=("total_points", "sum"), dnfs=("classified", lambda s: (~s).sum()),
            avg_grid=("grid", "mean"), avg_finish=("position", "mean"),
        )
        .reset_index()
    )

    agg_constructor_career = (
        fact_results.groupby("constructor_family")
        .agg(
            races=("raceId", "nunique"), wins=("is_win", "sum"), podiums=("is_podium", "sum"),
            points=("total_points", "sum"), first_season=("season", "min"), last_season=("season", "max"),
        )
        .reset_index()
    )
    agg_constructor_career = agg_constructor_career.merge(
        constructor_champ_counts, left_on="constructor_family", right_index=True, how="left"
    )
    agg_constructor_career["championships"] = agg_constructor_career["championships"].fillna(0).astype(int)

    agg_constructor_season = (
        fact_results.groupby(["season", "constructor_family"])
        .agg(races=("raceId", "nunique"), wins=("is_win", "sum"), podiums=("is_podium", "sum"),
             points=("total_points", "sum"))
        .reset_index()
    )

    # ----------------------------------------------------------------- #
    # Circuit stats
    # ----------------------------------------------------------------- #
    print("Building circuit stats...")
    agg_circuit_stats = (
        fact_results.merge(dim_races[["raceId", "circuitId", "circuitName"]], on="raceId", how="left")
        .groupby(["circuitId", "circuitName"])
        .agg(
            races_held=("raceId", "nunique"),
            first_year=("season", "min"),
            last_year=("season", "max"),
            avg_finishers=("classified", lambda s: s.sum() / s.count() * 100),
        )
        .reset_index()
    )
    overtake_proxy = (
        fact_results[fact_results["grid"] > 0]
        .assign(abs_change=lambda d: (d["grid"] - d["position"]).abs())
        .merge(dim_races[["raceId", "circuitId"]], on="raceId", how="left")
        .groupby("circuitId")["abs_change"].mean()
        .rename("avg_position_change")
    )
    agg_circuit_stats = agg_circuit_stats.merge(overtake_proxy, on="circuitId", how="left")
    agg_circuit_stats = agg_circuit_stats.merge(
        dim_circuits[["circuitId", "lat", "long", "locality", "circuitCountry"]], on="circuitId", how="left"
    )

    # ----------------------------------------------------------------- #
    # Write parquet outputs
    # ----------------------------------------------------------------- #
    tables = {
        "dim_drivers": dim_drivers,
        "dim_constructors": dim_constructors,
        "dim_circuits": dim_circuits,
        "dim_races": dim_races,
        "fact_results": fact_results,
        "fact_sprint_results": fact_sprint_results,
        "fact_qualifying": fact_qualifying,
        "fact_pitstops": fact_pitstops,
        "fact_lap_times": fact_lap_times,
        "agg_lap_times": agg_lap_times,
        "driver_standings_progression": driver_standings_progression,
        "constructor_standings_progression": constructor_standings_progression,
        "season_champions": season_champions,
        "agg_driver_career": agg_driver_career,
        "agg_driver_season": agg_driver_season,
        "agg_constructor_career": agg_constructor_career,
        "agg_constructor_season": agg_constructor_season,
        "agg_circuit_stats": agg_circuit_stats,
    }
    print("Writing parquet files to", OUT_DIR)
    for name, df in tables.items():
        path = OUT_DIR / f"{name}.parquet"
        df.to_parquet(path, index=False)
        print(f"  {name:35s} {df.shape[0]:>8,} rows  x {df.shape[1]:>2} cols  -> {path.name}")

    print("\nDone.")


if __name__ == "__main__":
    main()
