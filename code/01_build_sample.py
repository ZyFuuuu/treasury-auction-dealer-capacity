"""
Download U.S. Treasury auction results and build the locked estimation sample.

Source: Treasury Fiscal Data API, auctions_query endpoint.
        https://fiscaldata.treasury.gov/datasets/treasury-securities-auctions-data/

The raw feed mixes nominal coupon securities with TIPS, floating-rate notes and
occasional special reopenings. TIPS auction yields are real rather than nominal,
so they must be removed by field rather than by eyeballing outliers.

Writes: data/raw/auctions_notes.csv
        data/raw/auctions_bonds.csv
        data/processed/sample_locked.csv
"""

import pathlib
import pandas as pd

RAW = pathlib.Path("data/raw")
OUT = pathlib.Path("data/processed")
RAW.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

BASE = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v1/accounting/od/auctions_query"
)

FIELDS = [
    "auction_date", "issue_date", "maturity_date", "cusip",
    "security_type", "security_term", "original_security_term",
    "reopening", "auction_format",
    "inflation_index_security", "floating_rate", "callable",
    "cash_management_bill_cmb",
    "offering_amt", "total_tendered", "total_accepted",
    "comp_tendered", "comp_accepted", "noncomp_accepted",
    "bid_to_cover_ratio", "high_yield", "low_yield", "avg_med_yield",
    "int_rate", "price_per100",
    "primary_dealer_tendered", "primary_dealer_accepted",
    "direct_bidder_tendered", "direct_bidder_accepted",
    "indirect_bidder_tendered", "indirect_bidder_accepted",
    "soma_included", "soma_tendered", "soma_accepted",
]

NUMERIC = [
    "offering_amt", "total_tendered", "total_accepted", "comp_tendered",
    "comp_accepted", "noncomp_accepted", "bid_to_cover_ratio", "high_yield",
    "low_yield", "avg_med_yield", "int_rate", "price_per100",
    "primary_dealer_tendered", "primary_dealer_accepted",
    "direct_bidder_tendered", "direct_bidder_accepted",
    "indirect_bidder_tendered", "indirect_bidder_accepted",
    "soma_tendered", "soma_accepted",
]

START = "2015-01-01"


def url(security_type: str) -> str:
    return (
        f"{BASE}?fields={','.join(FIELDS)}"
        f"&filter=auction_date:gte:{START},security_type:eq:{security_type}"
        f"&sort=auction_date&page[size]=10000&format=csv"
    )


def download() -> pd.DataFrame:
    frames = []
    for sec in ("Note", "Bond"):
        path = RAW / f"auctions_{sec.lower()}s.csv"
        if not path.exists():
            print(f"downloading {sec}s ...")
            pd.read_csv(url(sec)).to_csv(path, index=False)
        frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True)


def build(d: pd.DataFrame) -> pd.DataFrame:
    for col in ("auction_date", "issue_date", "maturity_date"):
        d[col] = pd.to_datetime(d[col])
    for col in NUMERIC:
        d[col] = pd.to_numeric(d[col], errors="coerce")

    print(f"{'starting rows':<46} {len(d):5d}")
    keep = pd.Series(True, index=d.index)
    steps = [
        ("inflation-indexed (TIPS)", d.inflation_index_security == "Yes"),
        ("floating-rate notes", d.floating_rate == "Yes"),
        ("callable", d.callable == "Yes"),
        ("cash management bills", d.cash_management_bill_cmb == "Yes"),
        ("auction not yet held", d.high_yield.isna() | d.bid_to_cover_ratio.isna()),
        ("special reopenings < $1bn", d.total_accepted <= 1e9),
    ]
    for label, mask in steps:
        dropped = (keep & mask).sum()
        keep &= ~mask
        print(f"  drop {label:<40} -{dropped:4d}   remaining {keep.sum():5d}")

    s = d[keep].copy()

    # Allotment shares use total accepted as the denominator. Auction size uses
    # the announced offering amount, which is known to the market in advance;
    # total accepted includes SOMA add-ons and noncompetitive bids settled later.
    s["pd_share"] = s.primary_dealer_accepted / s.total_accepted
    s["ind_share"] = s.indirect_bidder_accepted / s.total_accepted
    s["dir_share"] = s.direct_bidder_accepted / s.total_accepted
    s["soma_share"] = s.soma_accepted.fillna(0) / s.total_accepted
    s["size_bn"] = s.total_accepted / 1e9
    s["offer_bn"] = s.offering_amt / 1e9

    # Dispersion of accepted bids, constructed entirely within the auction.
    # This is NOT the conventional auction tail, which compares the stop yield
    # with the pre-auction when-issued yield.
    s["tail_bp"] = (s.high_yield - s.avg_med_yield) * 100

    return s


if __name__ == "__main__":
    sample = build(download())
    sample.to_csv(OUT / "sample_locked.csv", index=False)
    print(
        f"\nlocked sample: {len(sample)} auctions, "
        f"{sample.auction_date.min().date()} to {sample.auction_date.max().date()}"
    )
    print(sample.groupby("original_security_term").size().to_string())
