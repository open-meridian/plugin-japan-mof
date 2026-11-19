# Setup

## Launching it

The Ministry's data need no key and no account. Launch the plugin and approve
its one role, `data`. It reads the current month at once, and every hour
after; an earlier day only when the lake asks for it.

Its settings: the **Raw responses window** and **past the window** (the
SDK's), and on a deployment installed for development, **Sample data**: the
Ministry's answers recorded on 19 November 2026, committed with the plugin.

## Its dataset

On the deployment's **Data sources** page (deployment admins), for
`<instance>:mof_curves`:

1. **License it.** The dataset describes the Ministry's terms in words and
   declares no licence ([terms](terms.md)): the Public Data License
   (Version 1.0), with a source citation; the rates are calculated from the
   Japan Securities Dealers Association's prices, whose own terms the
   Ministry's pages do not state. Until a licence is set, the lake keeps the
   rows and reads every use right restrictively.
2. **Entitle** each plugin that reads it.
3. **Priority**, where another dataset states the same values.

## The record

The curve is about a record named by a code at `mof`: `mof:JGB Interest
Rate`. The platform does not seed it yet, and the plugin never makes one:
the Datasets page's Records tab shows it as not held, and its values wait
until your deployment holds it.
