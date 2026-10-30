"""
Event study, regressions and figures.

Reads  data/processed/sample_locked.csv
       data/processed/dealer_positions.csv
       data/raw/fred_yields.csv   (DGS2 DGS3 DGS5 DGS7 DGS10 DGS20 DGS30, daily)

Writes figures/figure1.png, figures/figure2.png and prints every number that
appears in the paper.

Two measurement choices worth flagging.

The trading-day index for the event windows is built from non-missing yield
observations. FRED carries a row for every weekday including federal holidays,
with the value left blank. Indexing on calendar rows instead drops any auction
whose window touches a holiday, which cost roughly 40% of the sample before
this was fixed.

Dealer inventory is standardised within maturity x year. Dealer positions have a
strong secular trend, so a regression on raw dollar inventory with year fixed
effects largely compares two trend lines rather than within-year variation.
"""

import pathlib
from math import sqrt

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

PROC = pathlib.Path("data/processed")
RAW = pathlib.Path("data/raw")
FIG = pathlib.Path("figures")
FIG.mkdir(exist_ok=True)

YIELD_COL = {
    "2-Year": "DGS2", "3-Year": "DGS3", "5-Year": "DGS5", "7-Year": "DGS7",
    "10-Year": "DGS10", "20-Year": "DGS20", "30-Year": "DGS30",
}
INV_COL = {
    "2-Year": "PDPOSGSC-L2", "3-Year": "PDPOSGSC-G2L3",
    "5-Year": "PDPOSGSC-G3L6", "7-Year": "PDPOSGSC-G6L7",
    "10-Year": "PDPOSGSC-G7L11", "20-Year": "LONG", "30-Year": "LONG",
}
OUTCOMES = {
    "tail_bp": "High-minus-median spread (bp)",
    "bid_to_cover_ratio": "Bid-to-cover ratio",
    "pd_share": "Dealer allotment share",
}


def load():
    s = pd.read_csv(PROC / "sample_locked.csv", parse_dates=["auction_date"])
    w = pd.read_csv(PROC / "dealer_positions.csv", parse_dates=["date"]).set_index("date")
    y = pd.read_csv(RAW / "fred_yields.csv", parse_dates=["observation_date"])
    y = y.rename(columns={"observation_date": "date"}).set_index("date").sort_index()
    s = s[s.original_security_term.isin(YIELD_COL)].copy()
    s["ycol"] = s.original_security_term.map(YIELD_COL)
    s["icol"] = s.original_security_term.map(INV_COL)
    s["yr"] = s.auction_date.dt.year
    return s, w.sort_index(), y


def yield_change(row, y, lo, hi):
    """Yield change from lo to hi trading days around the auction, in bp."""
    ser = y[row.ycol].dropna()
    idx = ser.index
    pos = idx.searchsorted(row.auction_date)
    if pos >= len(idx):
        return np.nan
    if idx[pos] != row.auction_date:   # auction fell on a non-trading day
        pos -= 1
    if pos + lo < 0 or pos + hi >= len(idx):
        return np.nan
    return (ser.iloc[pos + hi] - ser.iloc[pos + lo]) * 100


def event_study(s, y):
    print("=" * 74)
    print("AUCTION CYCLE: pre-auction yield run-up, three event windows")
    print("positive = yields rose into the auction = price concession")
    print("=" * 74)
    print(f"{'maturity':10s}{'N':>5s}" + "".join(f"{w:>18s}" for w in
          ("t-5 -> t0", "t-6 -> t-1", "t-10 -> t0")))
    for term in YIELD_COL:
        sub = s[s.original_security_term == term]
        row = f"{term:10s}"
        for i, (lo, hi) in enumerate([(-5, 0), (-6, -1), (-10, 0)]):
            v = pd.Series([yield_change(r, y, lo, hi) for _, r in sub.iterrows()]).dropna()
            t = v.mean() / (v.std() / sqrt(len(v)))
            if i == 0:
                row += f"{len(v):>5d}"
            row += f"{v.mean():>11.2f} (t={t:5.2f})"
        print(row)


def panel(s, w, y):
    """Attach matched-maturity inventory and standardise within maturity x year."""
    inv = []
    for _, r in s.iterrows():
        hist = w[r.icol].loc[: r.auction_date - pd.Timedelta(days=1)]
        inv.append(hist.iloc[-1] / 1e3 if len(hist) else np.nan)
    s = s.assign(inv_bn=inv)
    s["runup"] = [yield_change(r, y, -5, 0) for _, r in s.iterrows()]
    g = s.groupby(["original_security_term", "yr"])
    s["inv_z"] = (s.inv_bn - g.inv_bn.transform("mean")) / g.inv_bn.transform("std")
    s["relsize"] = s.offer_bn / g.offer_bn.transform("mean")
    for c in ("ind_share", "dir_share"):
        s[c[:3] + "_z"] = (s[c] - g[c].transform("mean")) / g[c].transform("std")
    return s.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["inv_z", "relsize", "ind_z", "dir_z"] + list(OUTCOMES)
    )


def fit(formula, data):
    return smf.ols(formula, data=data).fit(
        cov_type="cluster", cov_kwds={"groups": data.auction_date}
    )


def main_regressions(p):
    print("\n" + "=" * 74)
    print("DEALER INVENTORY AND AUCTION OUTCOMES")
    print(f"SE clustered by auction date, N = {len(p)}")
    print("=" * 74)
    specs = [
        ("(1) inventory only", "{} ~ inv_z"),
        ("(2) + relative size", "{} ~ inv_z + relsize"),
        ("(3) + maturity FE", "{} ~ inv_z + relsize + C(original_security_term)"),
        ("(4) + maturity, year FE",
         "{} ~ inv_z + relsize + C(original_security_term) + C(yr)"),
    ]
    for dv, label in OUTCOMES.items():
        print(f"\n--- {label} ---")
        for name, f in specs:
            m = fit(f.format(dv), p)
            print(f"  {name:26s} {m.params['inv_z']:+9.4f} "
                  f"(t = {m.tvalues['inv_z']:+5.2f})   R2 = {m.rsquared:.3f}")

    print("\n" + "=" * 74)
    print("WHAT THE SAMPLE CAN RULE OUT  [specification (4)]")
    print("=" * 74)
    for dv, label in OUTCOMES.items():
        m = fit("{} ~ inv_z + relsize + C(original_security_term) + C(yr)".format(dv), p)
        lo, hi = m.conf_int().loc["inv_z"]
        mu = p[dv].mean()
        print(f"\n{label}")
        print(f"  coefficient {m.params['inv_z']:+.4f}   95% CI [{lo:+.4f}, {hi:+.4f}]")
        print(f"  largest effect not ruled out: {max(abs(lo), abs(hi)):.4f} "
              f"= {100 * max(abs(lo), abs(hi)) / abs(mu):.2f}% of the mean ({mu:.3f})")


def split_sample(p):
    print("\n" + "=" * 74)
    print("IS THE NULL AN ARTEFACT OF DEALERS LEAVING THE AUCTION?")
    print("=" * 74)
    p = p.assign(early=(p.yr <= 2019).astype(int))
    for dv in ("tail_bp", "bid_to_cover_ratio"):
        print(f"\n--- {OUTCOMES[dv]} ---")
        for label, sub in (("2015-2019", p[p.early == 1]), ("2020-2026", p[p.early == 0])):
            share = sub.pd_share.mean()
            m = fit(f"{dv} ~ inv_z + relsize + C(original_security_term) + C(yr)", sub)
            print(f"  {label}  N={len(sub):3d}  mean dealer share {share:.1%}  "
                  f"inv_z = {m.params['inv_z']:+.4f} (t = {m.tvalues['inv_z']:+5.2f})")
        m = fit(f"{dv} ~ inv_z*early + relsize + C(original_security_term) + C(yr)", p)
        print(f"  interaction inv_z x early = {m.params['inv_z:early']:+.4f} "
              f"(t = {m.tvalues['inv_z:early']:+.2f})")


def demand_composition(p):
    print("\n" + "=" * 74)
    print("DEMAND COMPOSITION")
    print("Bidder shares are determined jointly with the auction outcome.")
    print("These are descriptive associations, not causal effects.")
    print("=" * 74)
    for dv in ("tail_bp", "bid_to_cover_ratio"):
        m = fit(f"{dv} ~ ind_z + dir_z + inv_z + relsize "
                f"+ C(original_security_term) + C(yr)", p)
        print(f"\n{OUTCOMES[dv]}   N = {int(m.nobs)}   R2 = {m.rsquared:.3f}")
        for k in ("ind_z", "dir_z", "inv_z", "relsize"):
            print(f"   {k:9s} {m.params[k]:+9.4f} (t = {m.tvalues[k]:+5.2f})")


def figure1(s):
    fig, ax = plt.subplots(1, 2, figsize=(11.5, 4.2))
    s = s.sort_values("auction_date")
    for col, label, colour in (("pd_share", "Primary dealers", "#c44e52"),
                               ("ind_share", "Indirect bidders", "#4c72b0"),
                               ("dir_share", "Direct bidders", "#55a868")):
        ax[0].plot(s.auction_date, s[col].rolling(30, min_periods=10).mean(),
                   lw=1.9, color=colour, label=label)
    ax[0].set_ylabel("Share of total accepted")
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].set_title("Panel A. Auction allotment by bidder type", fontsize=10)
    ax[0].grid(alpha=.25)
    ax[1].scatter(s.auction_date, s.tail_bp, s=6, alpha=.3, color="#999999")
    ax[1].plot(s.auction_date, s.tail_bp.rolling(30, min_periods=10).mean(),
               lw=2, color="#c44e52")
    ax[1].set_ylabel("Basis points")
    ax[1].set_title("Panel B. High-minus-median accepted yield", fontsize=10)
    ax[1].grid(alpha=.25)
    fig.suptitle(f"Nominal fixed-rate Treasury coupon auctions, 2015-2026 "
                 f"(N = {len(s)}); 30-auction moving average", fontsize=9, y=1.0)
    plt.tight_layout()
    plt.savefig(FIG / "figure1.png", dpi=135)
    plt.close()


def figure2(s, y):
    fig, ax = plt.subplots(figsize=(7.6, 4.5))
    for term, colour in (("2-Year", "#999999"), ("5-Year", "#55a868"),
                         ("10-Year", "#c44e52"), ("30-Year", "#4c72b0")):
        paths = []
        for _, r in s[s.original_security_term == term].iterrows():
            window = {k: yield_change(r, y, 0, k) for k in range(-5, 6)}
            if not any(pd.isna(v) for v in window.values()):
                paths.append(window)
        d = pd.DataFrame(paths)
        k = list(range(-5, 6))
        mean = [d[i].mean() for i in k]
        se = [d[i].std() / sqrt(len(d)) for i in k]
        ax.plot(k, mean, marker="o", ms=4, color=colour, lw=1.9,
                label=f"{term} (N={len(d)})")
        ax.fill_between(k, [m - e for m, e in zip(mean, se)],
                        [m + e for m, e in zip(mean, se)], color=colour, alpha=.12)
    ax.axvline(0, color="k", lw=.9, ls="--")
    ax.axhline(0, color="k", lw=.6)
    ax.set_xlabel("Trading days relative to auction")
    ax.set_ylabel("Yield change vs auction day (bp)")
    ax.set_title("Treasury auction cycle, 2015-2026\nshaded = plus/minus one "
                 "standard error", fontsize=10)
    ax.legend(frameon=False, fontsize=9)
    ax.grid(alpha=.25)
    plt.tight_layout()
    plt.savefig(FIG / "figure2.png", dpi=140)
    plt.close()


if __name__ == "__main__":
    s, w, y = load()
    event_study(s, y)
    p = panel(s, w, y)
    main_regressions(p)
    split_sample(p)
    demand_composition(p)
    figure1(s)
    figure2(s, y)
    print("\nfigures written to figures/")
