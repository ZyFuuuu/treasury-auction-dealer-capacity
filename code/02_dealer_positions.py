"""
Download primary dealer Treasury coupon positions by maturity bucket and stitch
the reporting segments into one continuous weekly series.

Source: New York Fed Primary Dealer Statistics (FR 2004).
        https://markets.newyorkfed.org/api/pd/get/{segment}/timeseries/{key}.csv

Two things make this less mechanical than it looks.

1. The API does not accept several series keys in one request. Each key is its
   own call.

2. The reporting categories change across segments. Through 2021 the long end is
   a single bucket for maturities above 11 years (PDPOSGSC-G11). From 2022 it is
   split into 11-21 years and above 21 years. To keep one comparable long-end
   measure across the whole sample, the two newer buckets are summed.

Writes: data/raw/pd_{segment}_{key}.csv
        data/processed/dealer_positions.csv
"""

import pathlib
import pandas as pd

RAW = pathlib.Path("data/raw")
OUT = pathlib.Path("data/processed")
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

BASE = "https://markets.newyorkfed.org/api/pd/get/{seg}/timeseries/{key}.csv"

# Positions in Treasury coupon securities excluding TIPS, by remaining maturity.
COMMON = [
    "PDPOSGSC-L2",      # <= 2 years
    "PDPOSGSC-G2L3",    # 2-3 years
    "PDPOSGSC-G3L6",    # 3-6 years
    "PDPOSGSC-G6L7",    # 6-7 years
    "PDPOSGSC-G7L11",   # 7-11 years
]
# Dealer financing. Largely suppressed for confidentiality after 2022, so these
# are downloaded for documentation rather than used in the baseline design.
FINANCING = ["PDSORA-UTSETTOT", "PDSIRRA-UTSETTOT"]

SEGMENTS = {
    "SBN2015": COMMON + ["PDPOSGSC-G11"] + FINANCING,
    "SBN2022": COMMON + ["PDPOSGSC-G11L21", "PDPOSGSC-G21"] + FINANCING,
    "SBN2024": COMMON + ["PDPOSGSC-G11L21", "PDPOSGSC-G21"] + FINANCING,
}


def download() -> pd.DataFrame:
    frames = []
    for seg, keys in SEGMENTS.items():
        for key in keys:
            path = RAW / f"pd_{seg}_{key}.csv"
            if not path.exists():
                print(f"downloading {seg} / {key} ...")
                pd.read_csv(BASE.format(seg=seg, key=key)).to_csv(path, index=False)
            frames.append(pd.read_csv(path))
    d = pd.concat(frames, ignore_index=True)
    d.columns = ["date", "series", "value"]
    d["date"] = pd.to_datetime(d["date"])
    # The API writes "*" where a cell would disclose an individual dealer.
    d["value"] = pd.to_numeric(d["value"], errors="coerce")
    return d.drop_duplicates(["date", "series"])


def stitch(d: pd.DataFrame) -> pd.DataFrame:
    w = d.pivot(index="date", columns="series", values="value").sort_index()
    # One long-end measure across the whole sample: the pre-2022 bucket where it
    # exists, otherwise the sum of the two post-2022 buckets.
    w["LONG"] = w["PDPOSGSC-G11"].fillna(
        w[["PDPOSGSC-G11L21", "PDPOSGSC-G21"]].sum(axis=1, min_count=2)
    )
    return w


if __name__ == "__main__":
    positions = stitch(download())
    positions.to_csv(OUT / "dealer_positions.csv")
    print(
        f"\n{len(positions)} weekly observations, "
        f"{positions.index.min().date()} to {positions.index.max().date()}"
    )
    missing = positions.isna().sum()
    print("\nmissing values by series (confidentiality suppression):")
    print(missing[missing > 0].to_string() if missing.any() else "  none")
