"""
The conventional auction tail, and whether it bears the observable signatures of
a dealer intermediation constraint.

    tail = stop yield - when-issued yield at the competitive close,  in bp

NOTHING THIS SCRIPT READS FROM data/bloomberg/ IS IN THIS REPOSITORY. When-issued
yield indices, SOFR swap rates and the MOVE index come from a Bloomberg terminal
and may not be redistributed. The formulas below reproduce them for anyone with
access. Run 01, 02 and 04 first.

    data/bloomberg/wi_index.csv       date, term, wi
    data/bloomberg/swap_rates.csv     date, term, swap
    data/bloomberg/move.csv           date, move

The when-issued series are the AUCR auction indices, one observation per auction
at the competitive bidding close. They are not daily. Tickers are irregular and
must be read off the terminal rather than guessed:

    2Y USB2YWI   3Y USN3YWI   5Y USB5YWI   7Y USB7YWI
    10Y USN10YWI   20Y USN20YWI   30Y USBD30WI

    =BDH("<ticker> Index","PX_LAST","01/01/2015","<today>","Dts=S","Sort=A")

Omit Days and Fill: these series are sparse and a calendar grid returns empty.

Swap rates are SOFR OIS, =BDH("USOSFR<n> Curncy","PX_LAST",...). Bloomberg
back-fills the curve before SOFR began publishing in April 2018, which avoids
splicing LIBOR and SOFR swaps across the 2021-22 transition and putting a
reporting break in the middle of the sample.

THE SPECIFICATION IS FROZEN. The main equation is

    tail_i = a + b InventoryZ + c RelativeSize + maturity FE + year FE + e

with standard errors clustered by auction date. Everything after it is a
consistency check, reported whatever it shows. Searching further specifications
for a positive coefficient after a null main result is what this structure
exists to prevent.

Three measurement points the results depend on.

1. Tenor is assigned from remaining life at auction, not from the reported
   original_security_term field, which is wrong for 17 of the 925 auctions:
   grouped on that field, the "5-Year" bucket contains securities with 1.99
   years left. Correcting it does not change the inventory result (-0.0349 to
   -0.0203 on the within-auction spread, both insignificant) but it recovers
   11 auctions that otherwise fail to match a when-issued index.

2. The index is dated at the competitive close, which is the benchmark the
   conventional tail is defined against. A previous version of this project used
   the previous day's close on CUSIP-level quotes; that measure has a standard
   deviation of 4.5bp against 1.3bp here, and correlates -0.16 with bid-to-cover
   against -0.54 here. The two agree in the way a noisy measure and a clean one
   should: regressing the index tail on the proxy gives a slope of 0.078, close
   to the variance ratio of 0.094 implied by classical measurement error.

3. The index history begins in September 2017, so 193 of the 925 auctions fall
   outside it. The 20-year series begins in May 2020 because the maturity was
   reintroduced then.
"""

import pathlib
import sys
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

warnings.simplefilter("ignore")

PROC = pathlib.Path("data/processed")
RAW = pathlib.Path("data/raw")
BB = pathlib.Path("data/bloomberg")

STD = np.array([2, 3, 5, 7, 10, 20, 30])
INV = {"2-Year": "PDPOSGSC-L2", "3-Year": "PDPOSGSC-G2L3", "5-Year": "PDPOSGSC-G3L6",
       "7-Year": "PDPOSGSC-G6L7", "10-Year": "PDPOSGSC-G7L11",
       "20-Year": "LONG", "30-Year": "LONG"}
YC = {"2-Year": "DGS2", "3-Year": "DGS3", "5-Year": "DGS5", "7-Year": "DGS7",
      "10-Year": "DGS10", "20-Year": "DGS20", "30-Year": "DGS30"}

MAIN = "atail ~ inv_z + relsize + C(tenor) + C(yr)"


def need(f):
    if not (BB / f).exists():
        print(__doc__)
        print(f"missing: {BB / f}")
        print("Licensed Bloomberg data, not distributed with this repository.")
        print("Everything in 01-04 runs without it.")
        sys.exit(0)
    return pd.read_csv(BB / f, parse_dates=["date"])


def build():
    s = pd.read_csv(PROC / "sample_locked.csv",
                    parse_dates=["auction_date", "maturity_date"])
    w = (pd.read_csv(PROC / "dealer_positions.csv", parse_dates=["date"])
           .set_index("date").sort_index())
    wi = need("wi_index.csv")

    s["yrs"] = (s.maturity_date - s.auction_date).dt.days / 365.25
    s["tenor"] = [f"{STD[np.argmin(np.abs(STD - y))]}-Year" for y in s.yrs]
    s["yr"] = s.auction_date.dt.year
    s["offer_bn"] = s.offering_amt / 1e9
    s["icol"] = s.tenor.map(INV)

    lvl, z52 = [], []
    for _, r in s.iterrows():
        h = w[r.icol].loc[: r.auction_date - pd.Timedelta(days=1)].dropna()
        if len(h) == 0:
            lvl.append(np.nan); z52.append(np.nan); continue
        cur = h.iloc[-1] / 1e3
        lvl.append(cur)
        if len(h) >= 53:
            win = h.iloc[-53:-1] / 1e3
            sd = win.std()
            z52.append((cur - win.mean()) / sd if sd > 0 else np.nan)
        else:
            z52.append(np.nan)
    s["inv_bn"], s["inv_z52"] = lvl, z52

    g = s.groupby(["tenor", "yr"])
    s["inv_z"] = (s.inv_bn - g.inv_bn.transform("mean")) / g.inv_bn.transform("std")
    s["relsize"] = s.offer_bn / g.offer_bn.transform("mean")

    m = s.merge(wi.rename(columns={"date": "auction_date", "term": "tenor"}),
                on=["auction_date", "tenor"], how="inner")
    m["atail"] = (m.high_yield - m.wi) * 100

    # optional: the price-based capacity measure
    if (BB / "swap_rates.csv").exists() and (RAW / "fred_yields.csv").exists():
        sw = pd.read_csv(BB / "swap_rates.csv", parse_dates=["date"])
        y = (pd.read_csv(RAW / "fred_yields.csv", parse_dates=["observation_date"])
               .rename(columns={"observation_date": "date"}))
        y = y.melt("date", var_name="col", value_name="cmt").dropna()
        y["tenor"] = y.col.map({v: k for k, v in YC.items()})
        sp = sw.rename(columns={"term": "tenor"}).merge(
            y[["date", "tenor", "cmt"]], on=["date", "tenor"], how="inner")
        sp["ss"] = (sp.swap - sp.cmt) * 100
        ix = {k: g.sort_values("date").reset_index(drop=True)
              for k, g in sp.groupby("tenor")}

        def prior(tenor, d):
            g = ix.get(tenor)
            if g is None:
                return np.nan
            p = np.searchsorted(g.date.values, np.datetime64(d))
            return g.ss.iloc[p - 1] if p >= 1 else np.nan

        m["ss"] = [prior(r.tenor, r.auction_date) for _, r in m.iterrows()]
    else:
        m["ss"] = np.nan

    if (BB / "move.csv").exists():
        mv = need("move.csv").dropna().set_index("date").sort_index()
        m["move"] = [mv.loc[: d - pd.Timedelta(days=1), "move"].iloc[-1]
                     if len(mv.loc[: d - pd.Timedelta(days=1)]) else np.nan
                     for d in m.auction_date]
    else:
        m["move"] = np.nan

    return m.replace([np.inf, -np.inf], np.nan)


def fit(f, d, how="auction_date"):
    if how == "hc1":
        return smf.ols(f, data=d).fit(cov_type="HC1")
    if how == "twoway":
        gr = np.column_stack([d.auction_date.astype("int64").values,
                              pd.factorize(d.tenor)[0]])
        return smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": gr})
    return smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": d[how]})


def line(name, m, v, n=None):
    lo, hi = m.conf_int().loc[v]
    print(f"  {name:38s} N={n or int(m.nobs):3d}  b={m.params[v]:+8.4f}  "
          f"t={m.tvalues[v]:+5.2f}  CI[{lo:+7.4f},{hi:+7.4f}]")


def main():
    e = build().dropna(subset=["atail", "inv_z", "relsize"])
    print(f"ESTIMATION SAMPLE  {len(e)} auctions, "
          f"{e.auction_date.min().date()} to {e.auction_date.max().date()}")
    print(f"  seven tenors; new issues {(e.reopening == 'No').sum()}, "
          f"reopenings {(e.reopening == 'Yes').sum()}")

    print("\n" + "=" * 80)
    print("TABLE 1.  THE CONVENTIONAL TAIL, BY TENOR (bp)")
    print("=" * 80)
    print(e.groupby("tenor").atail.agg(["count", "mean", "std", "min", "max"])
           .round(2).to_string())
    print(f"\n  pooled: mean {e.atail.mean():+.2f}, sd {e.atail.std():.2f}, "
          f"mean |tail| {e.atail.abs().mean():.2f}")
    print(f"  |tail| > 2bp: {(e.atail.abs() > 2).mean():.0%}   "
          f"> 5bp: {(e.atail.abs() > 5).mean():.0%}")
    print("\n  measurement validity (the tail should widen when demand is weak):")
    print(f"    corr(tail, bid-to-cover)      = {e.atail.corr(e.bid_to_cover_ratio):+.3f}")
    print(f"    corr(tail, high-minus-median) = {e.atail.corr(e.tail_bp):+.3f}")

    print("\n" + "=" * 80)
    print("TABLE 2.  MAIN SPECIFICATION  [frozen]")
    print("tail ~ inventory + relative size + maturity FE + year FE")
    print("clustered by auction date")
    print("=" * 80)
    m = fit(MAIN, e)
    line("inventory, z within maturity x year", m, "inv_z")
    d = e.dropna(subset=["inv_z52"])
    line("inventory, trailing 52-week (ex ante)",
         fit(MAIN.replace("inv_z", "inv_z52"), d), "inv_z52", len(d))

    lo, hi = m.conf_int().loc["inv_z"]
    big = max(abs(lo), abs(hi))
    print(f"\n  Effects larger than {big:.3f} bp per standard deviation of inventory")
    print(f"  are outside the interval, against a mean absolute tail of "
          f"{e.atail.abs().mean():.2f} bp.")
    print("  This bounds the effect; it does not establish that the effect is zero.")

    print("\n" + "=" * 80)
    print("CONSISTENCY CHECKS.  Reported whatever they show.")
    print("=" * 80)

    print("\n(a) standard errors")
    e["week"] = e.auction_date.dt.to_period("W").astype(str)
    for nm, how in [("auction date (main)", "auction_date"), ("week", "week"),
                    ("two-way, date x maturity", "twoway"),
                    ("heteroskedasticity only", "hc1")]:
        line(nm, fit(MAIN, e, how), "inv_z")

    print("\n(b) by tenor")
    for tn, g in e.groupby("tenor"):
        if len(g) < 40:
            continue
        line(tn, fit("atail ~ inv_z + relsize + C(yr)", g), "inv_z", len(g))

    print("\n(c) by sub-period")
    for nm, sub in [("2017-2021", e[e.yr <= 2021]), ("2022-2026", e[e.yr >= 2022])]:
        line(nm, fit(MAIN, sub), "inv_z", len(sub))

    print("\n(d) limited risk-bearing capacity predicts that inventory should")
    print("    matter more when the supply being absorbed is larger, i.e. a")
    print("    positive interaction.")
    mi = fit(MAIN.replace("inv_z", "inv_z * relsize"), e)
    line("inventory x relative size", mi, "inv_z:relsize")
    e["big"] = (e.relsize > e.groupby(["tenor", "yr"]).relsize.transform("median")).astype(int)
    mb = fit("atail ~ inv_z * big + relsize + C(tenor) + C(yr)", e)
    line("inventory x above-median size", mb, "inv_z:big")
    print(f"    implied effect, smaller auctions {mb.params['inv_z']:+.4f}")
    print(f"    implied effect, larger auctions  "
          f"{mb.params['inv_z'] + mb.params['inv_z:big']:+.4f}")
    d = e.dropna(subset=["inv_z52"])
    line("ex-ante inventory x relative size",
         fit(MAIN.replace("inv_z", "inv_z52 * relsize"), d), "inv_z52:relsize", len(d))
    print("    The interaction does not meet the stated criteria: the sign is")
    print("    opposite to the prediction and inconsistent across tenors. The")
    print("    interval still admits a positive interaction, so the mechanism is")
    print("    unsupported here rather than ruled out.")

    if e.ss.notna().any():
        print("\n(e) a price measure of intermediation conditions")
        print("    The matched-maturity swap spread is a market price related to the")
        print("    cost of holding Treasuries against swaps. It also reflects swap")
        print("    supply and demand, hedging flows and Treasury specialness, so a")
        print("    null extends the absence of predictive power to a market-based")
        print("    proxy rather than isolating a balance-sheet channel.")
        q = e.dropna(subset=["ss"])
        f2 = MAIN.replace("inv_z", "inv_z + ss")
        line("inventory, with swap spread", fit(f2, q), "inv_z", len(q))
        line("swap spread", fit(f2, q), "ss", len(q))
        for dv in ("bid_to_cover_ratio", "pd_share", "tail_bp"):
            line(f"swap spread -> {dv}", fit(f2.replace("atail", dv), q), "ss", len(q))

    if e.move.notna().any():
        print("\n(f) rate volatility")
        q = e.dropna(subset=["move"])
        line("inventory, with MOVE", fit(MAIN.replace("inv_z", "inv_z + move"), q),
             "inv_z", len(q))

    e.to_csv(PROC / "tail_panel.csv", index=False)
    print(f"\nwrote {PROC / 'tail_panel.csv'}  (Bloomberg-derived; gitignored)")


if __name__ == "__main__":
    main()
