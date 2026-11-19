# Licensed market data: what was obtained, and what could not be

Pulled from a Bloomberg terminal at the Haas School of Business, 4 and 6
November 2026. None of these series are in this repository: the terminal licence
prohibits redistribution, and `.gitignore` blocks the files and everything
derived from them. This file documents what exists locally so the results can be
audited and the inputs reproduced by anyone with terminal access.

---

## 1. When-issued yield indices (the primary benchmark)

```excel
=BDH("<ticker> Index","PX_LAST","01/01/2015","<today>","Dts=S","Sort=A")
```

One observation per auction, dated at the **competitive bidding close**, which is
the benchmark the conventional tail is defined against. These series are sparse,
not daily: omit `Days` and `Fill`, because a calendar grid returns an empty
column.

Tickers are irregular and must be read off `AUCR <GO>` (United States, filter the
Name column on "When Issued") rather than guessed. Four of the seven do not
follow the pattern of the other three:

| Tenor | Ticker | | Tenor | Ticker |
|---|---|---|---|---|
| 2Y | `USB2YWI` | | 10Y | `USN10YWI` |
| 3Y | `USN3YWI` | | 20Y | `USN20YWI` |
| 5Y | `USB5YWI` | | 30Y | `USBD30WI` |
| 7Y | `USB7YWI` | | | |

Do not use the `USII*` (inflation-indexed) or `USBL*` (bill) series.

**738 observations, September 2017 to November 2026**, 110 per tenor except the
20-year, which has 78 and begins in May 2020 when the maturity was reintroduced.
**733 match an auction in the locked sample**; of the sixteen that do not, four
are auctions held after the sample was downloaded and twelve failed to match
before the maturity-classification error described in the README was corrected.

### Validation

Every observation falls exactly on an auction date. The resulting tail has a
standard deviation of 1.27bp, a mean absolute value of 0.91bp, and no auction
beyond 5bp — the magnitudes a conventional tail should have. It correlates −0.54
with bid-to-cover and +0.45 with the within-auction high-minus-median spread,
both the signs the measure must have if it is capturing auction demand.

### Why the generic WI security line was not used

Bloomberg support confirmed that the pre-auction when-issued market for a new
issue trades on a temporary "WI" security line reachable through `AUCR`, but
that **those shell tickers are recycled after each auction cycle**. They are
reliable for the current window and are not a per-CUSIP historical record. The
AUCR indices are the durable series.

## 2. CUSIP-level when-issued quotes (retained as a cross-check)

```excel
=BDH("<cusip> Govt","YLD_YTM_MID",<start>,<end>,"Dts=S","Sort=A","Days=W","Fill=NA")
```

Pulled in three batches of 50, 47 and 42 securities, each converted to values
immediately after it resolved. `Days=W` and `Fill=NA` matter: the default
(`Fill=P`) silently carries the previous close onto non-trading days, and the
first test pull returned a value for 1 January 2015, a federal holiday, equal to
the 31 December 2014 close.

**139 CUSIPs, 9,606 daily quotes, January 2015 to October 2026.** Each security's
series correlates at least 0.972 with its matched constant-maturity yield
(median 0.994), which rules out block misalignment in the spreadsheet parse.

**New issues carry no pre-auction quote.** A new issue has no coupon until the
auction sets it, so the CUSIP is not a defined instrument beforehand and the
first observation is the auction day itself. Verified on 912828J27, a ten-year
note auctioned 11 February 2015 and issued 17 February: every weekday from 15
January to 10 February returns `#N/A`. Reopenings are unaffected. This is why
the CUSIP route can only measure 257 of the auctions, and why the AUCR indices
replaced it as the primary source.

Using the previous day's close, this measure gives a tail with a standard
deviation of 4.57bp against 1.27bp for the index, and a correlation with
bid-to-cover of −0.16 against −0.54. The two are consistent under classical
measurement error: regressing the index tail on the proxy gives a slope of 0.078
against the 0.094 implied by the variance ratio. The same-day close was rejected
as a benchmark because it is measured after the result is public, so differencing
against it removes the auction's own price impact.

## 3. SOFR overnight index swap rates

```excel
=BDH("USOSFR<n> Curncy","PX_LAST","12/01/2014","11/04/2026","Dts=S","Sort=A","Days=W","Fill=NA")
```

for n in {5, 7, 10, 20, 30}. Roughly 3,060 daily values per tenor. Bloomberg
back-fills the curve before SOFR began publishing in April 2018, so one
convention covers the whole sample and no LIBOR-to-SOFR splice is needed.

`USSWAP10`, `USSW10` and `USSA10` all returned `#N/A` on this terminal; only the
`USOSFR` family resolved. A first attempt at all five tenors together returned
`#N/A N/A` on four and succeeded on retry, which was throttling rather than
entitlement.

Matched-maturity swap spreads (swap rate less the constant-maturity yield, bp):

| Tenor | N | Mean | SD | Min | Max |
|---|---:|---:|---:|---:|---:|
| 5Y | 2,964 | −23.9 | 8.0 | −44.3 | −4.6 |
| 7Y | 2,963 | −32.7 | 9.3 | −57.5 | −11.9 |
| 10Y | 2,961 | −34.9 | 11.1 | −61.5 | −12.2 |
| 20Y | 2,963 | −55.3 | 14.1 | −88.5 | −12.5 |
| 30Y | 2,961 | −67.9 | 14.4 | −110.7 | −31.0 |

Uniformly negative and deepening with maturity. The ten-year spread averages
−53bp in 2016 and −49bp in 2025, the two episodes usually read as balance-sheet
scarcity.

## 4. MOVE index

```excel
=BDH("MOVE Index","PX_LAST","12/01/2014","11/04/2026","Dts=S","Sort=A","Days=W","Fill=NA")
```

**3,021 daily values**, mean 79.7, range 36.6 to 198.7, taken at the close before
each auction. Proprietary to ICE BofA with no free equivalent. It enters the tail
regression at z = 3.95 and raises R-squared from 0.022 to 0.050.

---

## Request throttling

An Open License terminal limits how much history can be pulled. Leaving live BDH
formulas in a workbook is what exhausts it: every recalculation re-sends every
request. Each batch here was pasted as values immediately after it resolved, and
the Bloomberg ribbon's live-update option was turned off before opening any
workbook of formulas.

## Known limitations

**The intraday path is not observable.** The index gives one point per auction and
BDH does not reach intraday history across this sample, so nothing here speaks to
price pressure within the auction day.

**Post-auction windows are short for one auction in each security.** The
CUSIP-level pull ended three days after each security's last auction, so only the
middle reopening of each CUSIP has a usable post-auction window. Any statement
about post-auction reversal rests on 119 auctions at horizons of a few days and
cannot distinguish the absence of reversal from an intraday reversal already
complete by the close.

**The swap spread is not a pure balance-sheet measure.** It also reflects
swap-market supply and demand, pension duration hedging, and Treasury
specialness. A null bounds this channel; it does not isolate it.
