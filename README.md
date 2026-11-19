# Dealer Intermediation Capacity and U.S. Treasury Auction Pricing

Undergraduate research project, Economics 191, UC Berkeley, Fall 2026.

**[Read the results draft (PDF) →](paper/results_draft.pdf)** · [earlier proposal](paper/proposal_v2.pdf)

## Question

Do U.S. Treasury auctions clear at larger concessions when primary dealers enter
the auction already holding large inventories in the maturity being sold?

The mechanism is standard: dealers absorb new supply onto their balance sheets
before distributing it, so the price impact of issuance should depend on how much
intermediation capacity they have left. Rather than ask only whether one proxy is
significant, the project asks whether measurable auction concessions carry the
observable implications of limited dealer risk-bearing capacity at all.

## Data

| Source | Content | Frequency | Access |
|---|---|---|---|
| Treasury Fiscal Data API | Auction results: stop yield, median accepted yield, bid-to-cover, allotment by bidder type | Per auction | Public |
| NY Fed Primary Dealer Statistics (FR 2004) | Dealer Treasury coupon positions by maturity bucket | Weekly | Public |
| FRED | Constant-maturity Treasury yields, 2Y–30Y | Daily | Public |
| Bloomberg | AUCR when-issued yield indices by tenor; SOFR OIS swap rates; MOVE | Per auction / daily | **Licensed** |

Download URLs are in `code/01_build_sample.py` and `code/02_dealer_positions.py`;
the Bloomberg formulas and tickers are in the header of `code/05_tail.py` and in
`docs/licensed_data.md`. Bloomberg's terms prohibit redistribution, so those
series and anything derived from them are blocked by `.gitignore`. `05_tail.py`
states what it needs and exits with instructions when those inputs are absent;
everything else runs on public data alone.

### Sample

| Step | Dropped | Remaining |
|---|---:|---:|
| Treasury notes and bonds, auction date ≥ 2015-01-01 | — | 1,213 |
| Inflation-indexed securities (TIPS) | 142 | 1,071 |
| Floating-rate notes | 143 | 928 |
| Callable securities | 0 | 928 |
| Cash management bills | 0 | 928 |
| Auction not yet held at download | 1 | 927 |
| Special reopenings below $1bn | 2 | **925** |

925 nominal fixed-rate coupon auctions, 2015-01-12 through 2026-10-07, across
2-, 3-, 5-, 7-, 10-, 20- and 30-year maturities.

**Maturity is assigned from remaining life at auction, not from the reported
`original_security_term` field.** That field is wrong for 17 of the 925 records:
grouped on it, the "5-Year" bucket contains securities with 1.99 years left.
Correcting it leaves the results unchanged (the inventory coefficient on the
within-auction spread moves from −0.0349 to −0.0203, both insignificant) but
recovers 11 auctions that otherwise fail to match a when-issued index.

## What is in here

```
code/
  01_build_sample.py       download and filter auction results
  02_dealer_positions.py   download and stitch the three FR 2004 segments
  03_analysis.py           event study, auxiliary regressions, figures
  04_robustness.py         alternative clustering and eight inventory definitions
  05_tail.py               the conventional tail, swap spreads, mechanism tests
  06_regression_output.py  full estimation output behind every reported number
  07_exhibits.py           summary statistics, regression table, descriptive figure
docs/
  licensed_data.md         what was pulled from Bloomberg, and what could not be
output/
  regression_output.log    complete statsmodels summaries
  regression_table.csv     one tidy row per coefficient
paper/                     drafts
```

Run the scripts in order. `01`–`04` and `07` need only public data; `05` and `06`
additionally need the Bloomberg inputs.

## Measuring the tail

The conventional auction tail is the stop yield less the when-issued yield at the
competitive bidding close. Three measurement points decide what the results mean.

**New issues have no pre-auction quote under their own CUSIP.** A new issue has no
coupon until the auction sets it, so the security is not a defined instrument
beforehand; its first observation is the auction day itself. Reopenings are
unaffected. This is institutional, not a gap in the data.

**The benchmark comes from the Bloomberg AUCR when-issued yield indices**, one
observation per auction at the competitive close, which covers new issues and
reopenings alike: **733 of the 925 auctions, seven tenors, September 2017 onward**
(the 20-year series begins May 2020, when the maturity was reintroduced).

**An earlier CUSIP-level proxy is retained as a cross-check.** Using the previous
day's close on 9,606 security-level quotes gives a tail with a standard deviation
of 4.57bp against 1.27bp for the index measure, and correlations with bid-to-cover
of −0.16 against −0.54. The two agree the way a noisy measure and a clean one
should: regressing the index tail on the proxy gives a slope of 0.078, against the
0.094 implied by classical measurement error.

## Main results

**Concessions are measurable and small.** Across 733 auctions the mean signed tail
is +0.096bp, the standard deviation 1.268bp, and the mean absolute tail 0.912bp.
The tail correlates −0.54 with bid-to-cover, which is the sign the measure must
have if it is capturing auction demand.

**The auction cycle is present.** Constant-maturity yields rise into 10- and
30-year auctions by 2.66 and 2.99 basis points over the five trading days ending
on the auction date (t = 2.91 and 3.30), robust to a window ending one day
earlier. Measured on the security being sold rather than the fitted curve, the
10-year run-up is larger at 3.42bp (t = 3.5).

**Dealer inventory does not predict the tail.** In the baseline — maturity-matched
inventory from the last report published strictly before the auction,
standardised within maturity × year, with relative offering size and maturity and
year fixed effects, clustered by auction date — the coefficient is +0.0683bp per
standard deviation (SE 0.0534, z = 1.28, p = 0.201). It is nearly unchanged across
the nested specifications, insignificant across eight alternative definitions of
inventory and five clustering schemes, and insignificant in both halves of the
sample.

The 95% interval is [−0.036, +0.173], ruling out effects above about 19% of the
mean absolute tail. **The same specification detects rate volatility at z = 3.95**
and relative offering size at p = 0.001, so the null reflects the absence of a
relationship rather than a specification without power.

**Supply amplification is not supported.** Limited risk-bearing capacity predicts
that inventory should matter more when the auction is large. The interaction with
relative offering size is −0.8625 (z = −1.21), opposite in sign to the prediction;
an above-median-size indicator implies an inventory effect of +0.077 for smaller
auctions and +0.030 for larger ones. The intervals do not exclude every positive
interaction, so the mechanism is unsupported here rather than ruled out.

**A price measure of capacity adds nothing.** The matched-maturity SOFR swap
spread is available for 514 auctions at five tenors and is insignificant on the
tail (z = 0.54). On those same 514 auctions the inventory coefficient is +0.1141
without the swap spread and +0.1156 with it: the difference from the full-sample
estimate is almost entirely the sample restriction, not the control. The swap
spread also reflects swap supply and demand, hedging flows and Treasury
specialness, so this extends the absence of predictive power to a market-based
proxy rather than isolating a balance-sheet channel. Its interval is roughly three
times wider than the inventory bound.

**The long end is suggestive but not established.** At 20 and 30 years the tail
coefficients are +0.284 and +0.271 and the bid-to-cover coefficients are −0.0238
and −0.0202, directionally consistent across two outcomes. Across seven tenors and
two outcomes there are 14 tests, of which one meets 5% and two more approach it,
against 0.7 expected under a complete null. The structure is more interesting than
the count, but it does not support a long-end mechanism claim.

**What does move with pricing is the composition of demand.** A one-standard-
deviation increase in the indirect bidder share is associated with a 0.280bp lower
within-auction spread (t = −6.58) and the direct bidder share with 0.180bp
(t = −4.01). Bidder shares and auction outcomes are determined jointly, so these
are reported as descriptive.

## Scope

These results do not rule out dealer-specific constraints, intraday price
pressure, or risk measures absent from public data. They establish that the
inventory channel has limited observable support in this sample, over these
tenors, under these measures. The identification is conditional throughout: there
is no exogenous shock to dealer capacity, auction size is not randomly assigned,
and bidder shares are simultaneous with pricing.

## Note

Coursework in progress. Results may change as the project develops.
