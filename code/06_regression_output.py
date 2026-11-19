"""
Dump the full estimation output behind every number reported in the paper.

Writes
    output/regression_output.log    complete statsmodels summaries
    output/regression_table.csv     one tidy row per coefficient

Every specification in the paper appears here with its standard error, p-value,
confidence interval, N, R-squared, fixed effects and clustering, so that a
reader can rebuild any table without rerunning the estimation.

The main specification is clustered by AUCTION DATE. Clustering by week is a
consistency check, not the baseline; the two are reported separately and should
not be relabelled.
"""

import pathlib
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

warnings.simplefilter("ignore")

PROC = pathlib.Path("data/processed")
OUT = pathlib.Path("output")
OUT.mkdir(exist_ok=True)

MAIN = "atail ~ inv_z + relsize + C(tenor) + C(yr)"
ROWS = []
LOG = []


def fit(f, d, how="auction_date"):
    if how == "hc1":
        return smf.ols(f, data=d).fit(cov_type="HC1")
    if how == "twoway":
        gr = np.column_stack([d.auction_date.astype("int64").values,
                              pd.factorize(d.tenor)[0]])
        return smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": gr})
    return smf.ols(f, data=d).fit(cov_type="cluster", cov_kwds={"groups": d[how]})


def record(spec, dv, m, d, cluster, keep, full=False, note=""):
    """Append the tidy rows and, optionally, the complete summary to the log."""
    ci = m.conf_int()
    for k in keep:
        if k not in m.params.index:
            continue
        ROWS.append(dict(
            specification=spec, dependent=dv, term=k,
            coef=m.params[k], std_err=m.bse[k], t=m.tvalues[k], p=m.pvalues[k],
            ci_lo=ci.loc[k, 0], ci_hi=ci.loc[k, 1],
            n_obs=int(m.nobs), r_squared=m.rsquared,
            maturity_fe="C(tenor)" in m.model.formula,
            year_fe="C(yr)" in m.model.formula,
            cluster=cluster,
            n_clusters=(d[cluster].nunique() if cluster in d.columns else ""),
            note=note))
    if full:
        LOG.append("=" * 100)
        LOG.append(f"SPECIFICATION: {spec}")
        LOG.append(f"formula: {m.model.formula}")
        LOG.append(f"cluster: {cluster}"
                   + (f"   clusters: {d[cluster].nunique()}" if cluster in d.columns else ""))
        if note:
            LOG.append(f"note: {note}")
        LOG.append("=" * 100)
        LOG.append(str(m.summary()))
        LOG.append("")


def main():
    e = pd.read_csv(PROC / "tail_panel.csv", parse_dates=["auction_date"])
    e = e.dropna(subset=["atail", "inv_z", "relsize"])
    e["week"] = e.auction_date.dt.to_period("W").astype(str)
    e["month"] = e.auction_date.dt.to_period("M").astype(str)
    e["big"] = (e.relsize > e.groupby(["tenor", "yr"]).relsize.transform("median")).astype(int)

    LOG.append("ESTIMATION SAMPLE")
    LOG.append(f"  auctions           {len(e)}")
    LOG.append(f"  period             {e.auction_date.min().date()} to "
               f"{e.auction_date.max().date()}")
    LOG.append(f"  tenors             {sorted(e.tenor.unique())}")
    LOG.append(f"  new issues         {(e.reopening == 'No').sum()}")
    LOG.append(f"  reopenings         {(e.reopening == 'Yes').sum()}")
    LOG.append(f"  auction dates      {e.auction_date.nunique()}")
    LOG.append(f"  auction weeks      {e.week.nunique()}")
    LOG.append("")
    LOG.append("DEPENDENT VARIABLE  atail = (stop yield - when-issued yield at the")
    LOG.append("competitive close) x 100, in basis points.")
    LOG.append(e.atail.describe().round(4).to_string())
    LOG.append("")
    LOG.append("KEY REGRESSORS")
    LOG.append(e[["inv_z", "inv_z52", "relsize"]].describe().round(4).to_string())
    LOG.append("")

    # ---- main, reported in full -------------------------------------------
    record("M1 main: inventory", "atail", fit(MAIN, e), e, "auction_date",
           ["inv_z", "relsize"], full=True,
           note="frozen baseline; inventory standardised within maturity x year")

    d = e.dropna(subset=["inv_z52"])
    record("M2 main: ex-ante inventory", "atail",
           fit(MAIN.replace("inv_z", "inv_z52"), d), d, "auction_date",
           ["inv_z52", "relsize"], full=True,
           note="inventory as deviation from its own trailing 52 weeks")

    record("M3 inventory x relative size", "atail",
           fit(MAIN.replace("inv_z", "inv_z * relsize"), e), e, "auction_date",
           ["inv_z", "relsize", "inv_z:relsize"], full=True,
           note="limited risk-bearing capacity predicts a POSITIVE interaction")

    record("M4 inventory x above-median size", "atail",
           fit("atail ~ inv_z * big + relsize + C(tenor) + C(yr)", e), e,
           "auction_date", ["inv_z", "big", "inv_z:big", "relsize"], full=True,
           note="big = offering above the maturity-year median")

    # ---- consistency checks, tidy rows only --------------------------------
    for nm, how in [("week", "week"), ("month", "month"),
                    ("twoway", "twoway"), ("hc1", "hc1")]:
        record(f"C1 clustering: {nm}", "atail", fit(MAIN, e, how), e, nm,
               ["inv_z"], note="same point estimate as M1 by construction")

    for tn, g in e.groupby("tenor"):
        if len(g) < 40:
            continue
        record(f"C2 tenor: {tn}", "atail",
               fit("atail ~ inv_z + relsize + C(yr)", g), g, "auction_date",
               ["inv_z"], note="maturity FE dropped within a single tenor")

    for nm, sub in [("2017-2021", e[e.yr <= 2021]), ("2022-2026", e[e.yr >= 2022])]:
        record(f"C3 sub-period: {nm}", "atail", fit(MAIN, sub), sub,
               "auction_date", ["inv_z"])

    dd = e.dropna(subset=["inv_z52"])
    record("C4 ex-ante inventory x size", "atail",
           fit(MAIN.replace("inv_z", "inv_z52 * relsize"), dd), dd,
           "auction_date", ["inv_z52:relsize"])

    if e.move.notna().any():
        q = e.dropna(subset=["move"])
        record("C5 + MOVE", "atail", fit(MAIN.replace("inv_z", "inv_z + move"), q),
               q, "auction_date", ["inv_z", "move"], full=True)

    if e.ss.notna().any():
        q = e.dropna(subset=["ss"])
        # The swap spread exists only for 5, 7, 10, 20 and 30 years, so the
        # sample drops to 514. Estimate the baseline on that same subsample
        # first: the inventory coefficient moves because 2- and 3-year auctions
        # leave, not because the swap spread enters.
        record("S0 baseline on the swap subsample", "atail", fit(MAIN, q), q,
               "auction_date", ["inv_z"],
               note="same 514 auctions, swap spread NOT included")
        f2 = MAIN.replace("inv_z", "inv_z + ss")
        record("S1 + swap spread", "atail", fit(f2, q), q, "auction_date",
               ["inv_z", "ss", "relsize"], full=True,
               note="matched-maturity SOFR swap spread at the previous close, bp")
        for dv in ("bid_to_cover_ratio", "pd_share", "tail_bp"):
            record(f"S2 swap spread -> {dv}", dv,
                   fit(f2.replace("atail", dv), q), q, "auction_date",
                   ["inv_z", "ss"])
    else:
        LOG.append("=" * 100)
        LOG.append("SWAP SPREAD REGRESSIONS NOT ESTIMATED")
        LOG.append("tail_panel.csv has no non-missing swap spread. The spread is the")
        LOG.append("matched-maturity SOFR OIS rate less the constant-maturity Treasury")
        LOG.append("yield, so it needs data/raw/fred_yields.csv alongside")
        LOG.append("data/bloomberg/swap_rates.csv. Rerun 05_tail.py once both exist.")
        LOG.append("=" * 100)
        LOG.append("")

    t = pd.DataFrame(ROWS)
    t.to_csv(OUT / "regression_table.csv", index=False)

    LOG.append("=" * 100)
    LOG.append("TIDY COEFFICIENT TABLE (output/regression_table.csv)")
    LOG.append("=" * 100)
    show = t[["specification", "term", "coef", "std_err", "t", "p",
              "ci_lo", "ci_hi", "n_obs", "r_squared", "cluster"]].copy()
    for c in ["coef", "std_err", "t", "ci_lo", "ci_hi"]:
        show[c] = show[c].round(4)
    show["p"] = show.p.round(3)
    show["r_squared"] = show.r_squared.round(3)
    LOG.append(show.to_string(index=False))

    (OUT / "regression_output.log").write_text("\n".join(LOG) + "\n")
    print(f"wrote {OUT/'regression_output.log'} ({len(LOG)} lines)")
    print(f"wrote {OUT/'regression_table.csv'} ({len(t)} coefficient rows)")


if __name__ == "__main__":
    main()
