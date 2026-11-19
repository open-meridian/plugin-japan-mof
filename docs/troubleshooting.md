# Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| **Not answering** | No check has reached the Ministry's website | Check the deployment's outbound access to www.mof.go.jp; the plugin tries again within the hour |
| **Answering**, with a warning | An earlier check worked; the last did not | Nothing, usually: the next check runs within the hour |
| **1 record not held** | Your deployment holds no record for the JGB curve: the platform does not seed it yet | Nothing the plugin can do: it never makes a record. Its values are recorded once your deployment holds it |
| A day declined, *source silent* | A weekend, a holiday, a day not published yet | Wait for the Ministry's next publication, at 9:30 Tokyo time the next business day |
| A subject declined, *not covered* | Not this plugin's record | Check the Records tab |
| Datasets: **Not licensed yet** | No deployment admin has licensed the dataset | Ask a deployment admin to license it on Data sources |
