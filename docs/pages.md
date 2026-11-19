# Pages

Both pages are the data role's, under **Manage**, for the plugin's admins.
Neither shows a rate. Each is also a read tool on the deployment's MCP,
answering what the page shows.

## Connection (`read_connection`)

The head's status; **Key** (the mode, "No key needed"); **Limits and use**
(one request at a time, at most one every two seconds, a check every hour,
the history at most once a day; the requests made, the last check and
error); **Stream** (it does not stream); and **Sources**, a tab of its own:
the current month's file and the history, each with its state ("Pulled when
wanted" for the history until the lake asks for an earlier day), latest day
and calls, and in its details where it reads, when the Ministry publishes
and the answers kept.

## Datasets (`read_datasets`)

**Served**: its dataset as declared, whether it is licensed, what it
recorded and declined, and the wants it answered; then **Records**, a tab of
its own: the curve's record, what it is recorded as, its convention, and
your deployment's instrument for it or why there is none.
