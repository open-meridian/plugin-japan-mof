# Overview

Japan's Ministry of Finance publishes the rates this plugin puts into your
deployment's lake:

- **JGB interest rates** (`<instance>:mof_curves`): each business day, the
  Japanese Government Bonds' interest rates on a constant maturity basis at
  1 to 10, 15, 20, 25, 30 and 40 years, from 3pm closing prices.

It reads the Ministry's public website: no key, no account. It checks the
current month's file every hour; a day before the current month is read
from the history since 1974 when your lake asks for it.

## What it records

- **Each value as the Ministry writes it,** made an exact decimal from its
  text. A tenor the Ministry states nothing for is no value, never a zero.
- **Par yields.** Each rate is a par yield at its tenor on the curve's
  record, with semiannual compounding, as the Ministry states it. The
  Ministry states no day count; the plugin states the JGBs' own, NL/365.
- **Against your deployment's record.** The curve is asked of your
  deployment by a code at `mof`; the plugin never makes a record: if your
  deployment does not hold it, it is reported missing, and its values wait.
- **No published time:** the Ministry releases the rates at 9:30 a.m. Tokyo
  time the next business day, and states no time on a value.
- **Not carried:** forward rates and curve parameters, which are derived
  later from the points.

## What it never does

It records no trade and shows no value on its pages. It holds no account and
uses no key. It never edits a value.
