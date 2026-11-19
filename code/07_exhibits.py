"""
The exhibits for the results draft: summary statistics, the descriptive figure,
and the regression table, as LaTeX plus a rendered figure.

Writes
    output/table1_summary.tex
    output/table2_regression.tex
    figures/figure1_descriptive.png
"""

import pathlib
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

warnings.simplefilter("ignore")

PROC = pathlib.Path("data/processed")
OUT = pathlib.Path("output")
FIG = pathlib.Path("figures")
OUT.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)

MAIN = "atail ~ inv_z + relsize + C(tenor) + C(yr)"


def fit(f, d):
    return smf.ols(f, data=d).fit(cov_type="cluster",
                                  cov_kwds={"groups": d.auction_date})


# --------------------------------------------------------------- Table 1
def table1(e, s):
    rows = [
        ("Conventional auction tail (bp)", e.atail),
        ("High-minus-median spread (bp)", e.tail_bp),
        ("Bid-to-cover ratio", e.bid_to_cover_ratio),
        ("Primary dealer allotment share", e.pd_share),
        ("Indirect bidder share", e.ind_share),
        ("Direct bidder share", e.dir_share),
        ("Dealer inventory, $z$ within maturity $\\times$ year", e.inv_z),
        ("Dealer inventory, trailing 52-week deviation", e.inv_z52),
        ("Offering size relative to maturity-year mean", e.relsize),
        ("Offering size (\\$bn)", e.offer_bn),
    ]
    L = [r"\begin{table}[htbp]\centering",
         r"\caption{Summary statistics}", r"\label{tab:summary}",
         r"\footnotesize", r"\begin{tabular}{lrrrrrr}", r"\toprule",
         r"& $N$ & Mean & SD & p10 & Median & p90 \\", r"\midrule"]
    for name, v in rows:
        v = v.dropna()
        L.append(f"{name} & {len(v)} & {v.mean():.3f} & {v.std():.3f} & "
                 f"{v.quantile(.10):.3f} & {v.median():.3f} & {v.quantile(.90):.3f} \\\\")
    g = e.groupby("tenor").size()
    order = ["2-Year", "3-Year", "5-Year", "7-Year", "10-Year", "20-Year", "30-Year"]
    bytenor = ", ".join(f"{o.replace('-Year', 'Y')} {g.get(o, 0)}" for o in order)
    L += [r"\bottomrule", r"\end{tabular}",
          r"\begin{minipage}{0.95\textwidth}\vspace{4pt}\scriptsize",
          rf"\emph{{Notes.}} {len(e)} nominal fixed-rate coupon auctions, "
          rf"{e.auction_date.min():%B %Y} to {e.auction_date.max():%B %Y}, "
          r"drawn from the locked sample of "
          rf"{len(s)} auctions; the when-issued index begins in September 2017 and "
          r"the twenty-year series in May 2020, when that maturity was reintroduced. "
          r"The conventional tail is the stop yield less the when-issued yield at the "
          r"competitive bidding close. The high-minus-median spread is constructed "
          r"entirely within the auction and is not a tail. Maturity is assigned from "
          r"remaining life at auction rather than the reported original term field, "
          r"which is inconsistent for 17 records. Auctions by maturity: "
          + bytenor + ".",
          r"\end{minipage}", r"\end{table}"]
    (OUT / "table1_summary.tex").write_text("\n".join(L) + "\n")
    print(f"table1_summary.tex   {len(rows)} variables, N = {len(e)}")


# --------------------------------------------------------------- Table 2
def table2(e):
    specs = [
        ("(1)", "atail ~ inv_z", "inv_z", False, False),
        ("(2)", "atail ~ inv_z + relsize", "inv_z", False, False),
        ("(3)", "atail ~ inv_z + relsize + C(tenor)", "inv_z", True, False),
        ("(4)", MAIN, "inv_z", True, True),
        ("(5)", MAIN.replace("inv_z", "inv_z52"), "inv_z52", True, True),
        ("(6)", MAIN.replace("inv_z", "inv_z + move"), "inv_z", True, True),
    ]
    ms = [(lab, fit(f, e), v, fe, ye) for lab, f, v, fe, ye in specs]

    def cell(m, k, dec=4):
        if k not in m.params.index:
            return "", ""
        star = "^{***}" if m.pvalues[k] < .01 else "^{**}" if m.pvalues[k] < .05 \
            else "^{*}" if m.pvalues[k] < .1 else ""
        return f"${m.params[k]:+.{dec}f}{star}$", f"$({m.bse[k]:.{dec}f})$"

    L = [r"\begin{table}[htbp]\centering",
         r"\caption{Dealer inventory and the conventional auction tail}",
         r"\label{tab:main}", r"\footnotesize",
         r"\begin{tabular}{lcccccc}", r"\toprule",
         "& " + " & ".join(lab for lab, *_ in ms) + r" \\", r"\midrule"]
    for key, name in [("inv_z", r"Dealer inventory ($z$)"),
                      ("inv_z52", r"Dealer inventory (trailing 52wk)"),
                      ("relsize", "Relative offering size"),
                      ("move", "MOVE index")]:
        b = [cell(m, key)[0] for _, m, *_ in ms]
        s = [cell(m, key)[1] for _, m, *_ in ms]
        if not any(b):
            continue
        L.append(f"{name} & " + " & ".join(b) + r" \\")
        L.append(" & " + " & ".join(s) + r" \\[2pt]")
    L.append(r"\midrule")
    L.append("Maturity fixed effects & " + " & ".join(
        r"\checkmark" if fe else "" for *_, fe, _ in ms) + r" \\")
    L.append("Year fixed effects & " + " & ".join(
        r"\checkmark" if ye else "" for *_, ye in ms) + r" \\")
    L.append("Auctions & " + " & ".join(str(int(m.nobs)) for _, m, *_ in ms) + r" \\")
    L.append("$R^2$ & " + " & ".join(f"{m.rsquared:.3f}" for _, m, *_ in ms) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}",
          r"\begin{minipage}{0.95\textwidth}\vspace{4pt}\scriptsize",
          r"\emph{Notes.} The dependent variable is the conventional auction tail in "
          r"basis points: the stop yield less the when-issued yield at the competitive "
          r"bidding close, from the Bloomberg auction indices. Dealer inventory is the "
          r"primary dealer position in the maturity bucket matching the security, taken "
          r"from the last FR 2004 report published strictly before the auction. Column "
          r"(5) replaces the within-cell standardisation with the deviation from the "
          r"security's own trailing 52 weeks, which uses only information available on "
          r"the day of the auction. Standard errors in parentheses, clustered by auction "
          r"date (695 clusters). $^{*}$, $^{**}$ and $^{***}$ denote significance at the "
          r"10, 5 and 1 percent levels.",
          r"\end{minipage}", r"\end{table}"]
    (OUT / "table2_regression.tex").write_text("\n".join(L) + "\n")
    for lab, m, v, *_ in ms:
        print(f"  {lab}  {v:8s} b={m.params[v]:+.4f}  se={m.bse[v]:.4f}  "
              f"t={m.tvalues[v]:+.2f}  N={int(m.nobs)}  R2={m.rsquared:.3f}")


# -------------------------------------------------------------- Figure 1
def figure1(s, e):
    fig, ax = plt.subplots(1, 2, figsize=(11.2, 4.1))
    s = s.sort_values("auction_date")
    for col, label, colour in (("pd_share", "Primary dealers", "#c44e52"),
                               ("ind_share", "Indirect bidders", "#4c72b0"),
                               ("dir_share", "Direct bidders", "#55a868")):
        ax[0].plot(s.auction_date, s[col].rolling(30, min_periods=10).mean(),
                   lw=1.9, color=colour, label=label)
    ax[0].set_ylabel("Share of total accepted")
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].set_title("A. Who takes the supply", fontsize=10)
    ax[0].grid(alpha=.25)

    d = e.sort_values("auction_date")
    ax[1].scatter(d.auction_date, d.atail, s=7, alpha=.35, color="#999999")
    ax[1].plot(d.auction_date, d.atail.rolling(30, min_periods=10).mean(),
               lw=2, color="#c44e52")
    ax[1].axhline(0, color="k", lw=.6)
    ax[1].set_ylabel("Basis points")
    ax[1].set_title("B. The conventional auction tail", fontsize=10)
    ax[1].grid(alpha=.25)

    fig.suptitle("Panel A: 925 nominal fixed-rate coupon auctions, 2015-2026.  "
                 f"Panel B: {len(e)} auctions with a when-issued benchmark, 2017-2026.  "
                 "30-auction moving average.", fontsize=8.5, y=1.0)
    plt.tight_layout()
    plt.savefig(FIG / "figure1_descriptive.png", dpi=140)
    plt.close()
    print(f"figure1_descriptive.png   panel A N={len(s)}, panel B N={len(e)}")


if __name__ == "__main__":
    s = pd.read_csv(PROC / "sample_locked.csv", parse_dates=["auction_date"])
    e = pd.read_csv(PROC / "tail_panel.csv", parse_dates=["auction_date"])
    e = e.dropna(subset=["atail", "inv_z", "relsize"])
    table1(e, s)
    print("table2_regression.tex")
    table2(e)
    figure1(s, e)
