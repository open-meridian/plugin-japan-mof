# meridian-japan-mof

Japan's Ministry of Finance's JGB interest rates for
[Open Meridian](https://open-meridian.com): an Open Meridian plugin that puts
the Japanese Government Bonds' interest rates on a constant maturity basis,
1 to 40 years, into a deployment's lake. It reads the Ministry's interest
rate files and holds the `data` role, a data plugin. This is release 0.1.0,
a draft for the product owner. How to set it up and use it is in
[docs/](docs/README.md).

It is built on the SDK it pins, `open-meridian==0.36.0` (contract 30).

## What it records

- **`<instance>:mof_curves`** (pushed as published, and pulled): each
  business day's JGB interest rates at 1 to 10, 15, 20, 25, 30 and 40
  years, each a `par_yield` at its tenor on one curve record, in per cent as
  the Ministry writes them. Semiannual compounding, as the Ministry states
  it; NL/365 is the plugin's statement, since the Ministry states no day
  count. The current month is read every hour; a day before it from the
  history since 1974, when the lake wants it.
- **The record:** the curve is asked of the deployment by its code at `mof`
  (`mof:JGB Interest Rate`); the platform seeds none yet, so it is reported
  missing, never minted, and its rates wait.
- **Not presented:** forward rates and curve parameters (ruling 131: derived
  later from the points). No published time is recorded: the Ministry
  releases the rates at 9:30 the next business day and states no time on a
  value.

## Deploying it

On a deployment, with the `meridian` CLI connected (`meridian connect`):

    meridian plugin upload             # from this directory
    meridian plugin launch japan-mof   # a deployment admin approves its one role, data

No key and no account. A deployment admin then licenses its dataset and
entitles the plugins that read it on the Data sources page
([docs/setup.md](docs/setup.md)).

## Checking it

    make ci-local                  # lint, tests, plugin check, image, e2e: the pre-push gate
    make preview SHOTS=<dir>       # each page in a browser with the kit, at 375, 582 and 1280 px

`tests/test_suite.py` runs the SDK's data suite on the plugin's own
conversion, and it passes; a case about what the Ministry never states here
is not presented, with why.

## The terms, summarised

Not legal advice; read the Ministry's own words
([notice](https://www.mof.go.jp/english/about_mof/notice/index.html),
[interest rate Q&A](https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/qa.htm))
before relying on them. The Ministry's site content is under the Public Data
License (Version 1.0) unless otherwise provided: use, commercial use
included, with a source citation, and a statement where the content is
edited; numerical data and simple tables are outside its terms. The rates
are calculated from the Japan Securities Dealers Association's Reference
Statistical Prices, whose own terms the Ministry's pages do not state. The
dataset says so in words, and declares no licence: the deployment admin's
licence is the one enforced. This project is not affiliated with or
endorsed by the Ministry of Finance.

## Licence

Apache-2.0 (LICENSE, NOTICE). The Ministry's answers under
`src/japan_mof/responses/` are as received on 2026-11-19.
