# Dealer Intermediation Capacity and U.S. Treasury Auction Pricing

Undergraduate research project1, UC Berkeley, Fall 2026.

**[Read the paper (PDF) →](proposal_v2.pdf.pdf)**

## Question

Do U.S. Treasury auctions clear at larger price concessions when primary dealers
enter the auction already holding large inventories in the maturity being sold?

The mechanism is standard in the Treasury-market literature: dealers absorb new
supply onto their balance sheets before distributing it, so the price impact of
issuance should depend on how much intermediation capacity they have left. The
question here is whether that mechanism is still visible in auction pricing using
only publicly available data, in a period when primary dealers have become a much
smaller direct buyer at auction.

## Data

| Source | Content | Frequency | Access |
|---|---|---|---|
| Treasury Fiscal Data API | Auction results: stop yield, median accepted yield, bid-to-cover, allotment by bidder type | Per auction | Public |
| NY Fed Primary Dealer Statistics (FR 2004) | Dealer Treasury coupon positions by maturity bucket | Weekly | Public |
| FRED | Constant-maturity Treasury yields, 2Y–30Y | Daily | Public |

Download URLs are in `code/01_build_sample.py` and `code/02_dealer_positions.py`.

**Licensed data is excluded from this repository.** The project also uses
Bloomberg terminal data (pre-auction when-issued yields, the MOVE index, GCF repo
rates). Bloomberg's terms prohibit redistribution, so those series are not here
and are blocked by `.gitignore`. Results that depend on them are marked as such.

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

925 nominal fixed-rate coupon auctions, 2015-01-12 through 2026-10-07, covering
2-, 3-, 5-, 7-, 10-, 20- and 30-year maturities.

## What is in here

```
code/
  01_build_sample.py       download and filter auction results
  02_dealer_positions.py   download and stitch the three FR 2004 series segments
  03_analysis.py           event study, regressions, figures
data/
  processed/               the locked sample and the stitched dealer series
figures/
  figure1.png              allotment shares and the high-minus-median spread
  figure2.png              the auction cycle
paper/                     proposal drafts
```

Run the three scripts in order. `01` and `02` hit the public APIs; `03` reads what
they write and reproduces every number and figure in the paper.

## Main results so far

**The auction cycle is present in the recent sample.** Constant-maturity yields
rise into 10- and 30-year auctions by about 3 basis points over the five trading
days ending on the auction date (t = 2.91 and 3.30), and the result survives an
alternative window ending one day before the auction. Other maturities are
sensitive to the window definition, so the cross-maturity pattern is reported
but not interpreted.

**Dealer inventory does not explain auction pricing.** Maturity-matched dealer
inventory, standardised within maturity × year, is unrelated to the
high-minus-median accepted yield spread, the bid-to-cover ratio, or the dealer
allotment share, across four specifications and six maturity sectors.

The confidence intervals are tight enough for this to be informative rather than
simply inconclusive. With maturity and year fixed effects and standard errors
clustered by auction date, the 95% interval on the inventory coefficient for the
high-minus-median spread is [−0.118, +0.049] basis points, against a sample mean
spread of 5.25 basis points. Effects larger than roughly 2% of the mean can be
ruled out.

**The null is not an artefact of dealers' withdrawal from the auction.** Primary
dealers took 34.9% of accepted supply in 2015 and 10.2% in 2026. Splitting at
2019 does not recover an effect: the inventory coefficient is insignificant in
both halves and the interaction with an early-period indicator is flat. Even when
dealers still absorbed close to a third of supply, their aggregate inventory did
not predict auction pricing.

**What does move with pricing is the composition of demand**, not dealer
inventory. Indirect and direct bidder shares are strongly associated with both
the spread and the bid-to-cover ratio. These shares are determined jointly with
the auction outcome, so the association is reported as descriptive and not as a
causal effect.

## Open questions

The outcome variables used so far are built entirely from within the auction, so
they are free of macroeconomic news, but they are not the conventional auction
tail. That requires the pre-auction when-issued yield, which is Bloomberg data.
Whether the null survives a security-specific tail is the main remaining test.

## Note

This is coursework in progress. Results may change as the project develops.
