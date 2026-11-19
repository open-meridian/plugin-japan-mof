"""`make e2e`: the plugin on the plugin harness of the runtime it pins
(contract 30), beside `reader`, a reporting plugin (e2e/reader.py), and the
harness's admin. Run from the repository's root by the Makefile, which
builds the image and writes the harness's plugins first; standard library
only.

1. The website unreachable: the plugin's hosts file sends the Ministry's
   website nowhere, so its first check fails, and Connection says so --
   "Not answering", the data role's word -- and records nothing.
2. Sample data on (a developer's setting, accepted on the harness): the
   plugin reads the committed answers -- the current month to 18 November
   2026 -- and asks the deployment for the curve's record by its code at
   `mof`. The platform seeds none yet, so it is reported missing, never
   minted, and its values wait: the lake holds the one miss and no row
   (e2e/expected.lake's `miss|japan-mof|1`).
3. Parity: through the deployment's MCP, `read_connection` and
   `read_datasets` answer what the pages show, under the data role's names
   -- each file's latest day, the record with why it has none -- and core's
   `dashboard__list_datasets` lists `japan-mof:mof_curves` as the catalogue
   declares it: push and pull, Tokyo's day, no calendar, a day.
4. Licensed and entitled at the Data sources page: the reader is entitled.
5. `store lake` is e2e/expected.lake.
6. A new container: it reads the answers again and records nothing; a new
   process asks for the record once more and reports it missing again
   (`miss|japan-mof|2`), and reads its licences on start.
"""

import json
import os
import subprocess
import sys
import time

PROJECT = "mof-e2e"
LOG = ".e2e/runner.log"
COMPONENTS = ".e2e/components.log"
COMPOSE = ["docker", "compose", "-p", PROJECT, "-f", ".e2e/harness/compose.yaml",
           "-f", ".e2e/harness/plugins.yaml", "-f", "e2e/plugin.yaml"]
INSTANCE = "japan-mof"
CURVES = f"{INSTANCE}:mof_curves"
#: The curve's record, reported missing once a process.
MISSES = 1


class Failed(Exception):
    pass


def log(text):
    with open(LOG, "a", encoding="utf-8") as kept:
        kept.write(text + "\n")


def compose(*args, check=True, timeout=600):
    done = subprocess.run(COMPOSE + list(args), capture_output=True, text=True,
                          timeout=timeout)
    log(f"$ compose {' '.join(args)[:300]}\n{done.stdout[-4000:]}{done.stderr[-2000:]}")
    if check and done.returncode != 0:
        raise Failed(f"compose {' '.join(args)[:200]}: {(done.stdout + done.stderr).strip()[-600:]}")
    return done


def runner(*args, check=True):
    done = compose("run", "--rm", "-T", "runner", *args, check=check)
    return done.stdout if check else done


def must(condition, why):
    if not condition:
        raise Failed(why)


def until(seconds, attempt, what):
    deadline = time.monotonic() + seconds
    last = None
    while True:
        try:
            answer = attempt()
        except Failed as failed:
            answer, last = None, failed
        if answer:
            return answer
        if time.monotonic() > deadline:
            raise Failed(f"{what}, in {seconds} seconds" + (f": {last}" if last else ""))
        time.sleep(2)


def page(instance, level, path):
    said = runner("page", "--instance", instance, "--level", level, path)
    status, _, body = said.partition("\n")
    must(status.strip() == "200", f"{instance} {path} answered {said[-600:]}")
    return body


def call(tool, arguments=None):
    done = runner("mcp", "call", tool, json.dumps(arguments or {}), check=False)
    try:
        answer = json.loads(done.stdout)
    except ValueError:
        raise Failed(f"{tool}: no answer: {(done.stdout + done.stderr)[-400:]}")
    must(answer.get("outcome") in ("read", "unchanged"), f"{tool} answered {done.stdout[-700:]}")
    return answer["data"]


def store_lake():
    return compose("run", "--rm", "-T", "store", "lake").stdout


def sorted_lines(lines):
    return "\n".join(sorted(lines.strip().splitlines())) + "\n"


def run():
    started = time.time()
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    compose("up", "-d")
    runner("ready")
    runner("ready", "--instance", "reader")

    # 1. The website unreachable.
    page_said = runner("page", "--level", "admin", "/", "--until", "Not answering",
                       "--seconds", "90")
    must("Error" in page_said,
         f"step 1, Connection names why the Ministry was not reached: {page_said[-500:]}")
    lake = store_lake()
    must("row|" not in lake, f"step 1, nothing recorded with the website unreachable: {lake}")

    # 2. Sample data: the current month read, its record asked for and missed.
    runner("settings", "sample_data=true")
    runner("page", "--level", "admin", "/datasets?tab=records", "--until",
           'data-code="JGB Interest Rate"', "--seconds", "120")
    runner("page", "--level", "admin", "/?tab=sources", "--until", "Wed 18 Nov 2026",
           "--seconds", "60")
    until(90, lambda: f"miss|{INSTANCE}|{MISSES}" in store_lake(),
          "step 2, the curve's record was not reported missing")
    must("row|" not in store_lake(), "step 2, no row: the rates wait for the record")

    # 3. Parity through the deployment's MCP, and core's view of the catalogue.
    runner("grant", "--level", "admin")
    runner("mcp", "connect", "--covers", "deployment_admin", "--covers", f"{INSTANCE}:admin")
    tools = runner("mcp", "list").split()
    read_connection = next((t for t in tools if t.endswith("read_connection")), "")
    read_datasets = next((t for t in tools if t.endswith("read_datasets")), "")
    must(read_connection and read_datasets, f"step 3, the plugin's two tools are listed: {tools}")
    connection = call(read_connection)
    current, history = connection["sources"]
    must(connection["mode"] == "Sample data" and connection["credentials"] == []
         and connection["sessions"] is None
         and current["dataset"] == CURVES and current["last_release"] == "2026-11-18"
         and history["dataset"] == CURVES and history["state"] == "Pulled when wanted",
         f"step 3, read_connection: {connection}")
    datasets = call(read_datasets)
    records = {r["code"]: r for r in datasets["records"]}
    must(list(records) == ["JGB Interest Rate"]
         and records["JGB Interest Rate"]["miss"] == "not held: reported missing"
         and not records["JGB Interest Rate"]["instrument_id"],
         f"step 3, read_datasets names the record and why it has none: {datasets['records']}")
    shown = page(INSTANCE, "admin", "/datasets?tab=records")
    must(all(f'data-code="{code}"' in shown for code in records),
         "step 3, Datasets shows what read_datasets answers")
    listed = {d["dataset"]: d for d in call("dashboard__list_datasets")["datasets"]}
    entry = listed.get(CURVES, {}).get("catalogue_entry", {})
    must(entry.get("modes") == ["push", "pull"] and entry.get("day_time_zone") == "Asia/Tokyo"
         and entry.get("cadence") == 86400 and not entry.get("calendar_id")
         and entry.get("data_types") == ["meridian.v1.Rate"],
         f"step 3, core lists {CURVES} as declared: {listed.get(CURVES)}")

    # 4. Licensed and entitled.
    runner("licence", CURVES, "kept=true", "retention_days=0", "derived_use=true",
           "display=true", "personal_use=false",
           "note=The Ministry of Finance's JGB interest rates: use citing the Ministry.")
    runner("entitle", "--instance", "reader", CURVES, "note=The e2e's reader may read them.")
    runner("grant", "--instance", "reader", "--level", "read")

    # 5. The lake.
    got = sorted_lines(store_lake())
    with open(".e2e/lake", "w", encoding="utf-8") as kept:
        kept.write(got)
    with open("e2e/expected.lake", encoding="utf-8") as held:
        expected = held.read()
    if got != expected:
        diff = subprocess.run(["diff", "-u", "e2e/expected.lake", ".e2e/lake"], capture_output=True, text=True)
        raise Failed(f"step 5, the lake is not e2e/expected.lake:\n{diff.stdout[-3000:]}")

    # 6. A new container records nothing, and reports the record missing again.
    compose("up", "-d", "--no-deps", "--force-recreate", INSTANCE)
    runner("ready")
    until(120, lambda: "Wed 18 Nov 2026" in page(INSTANCE, "admin", "/?tab=sources"),
          "step 6, the new container did not read the answers again")
    until(90, lambda: f"miss|{INSTANCE}|{2 * MISSES}" in store_lake(),
          "step 6, the new container did not ask for the record again")
    time.sleep(5)
    again = sorted_lines(store_lake())
    must(again == got.replace(f"miss|{INSTANCE}|{MISSES}\n", f"miss|{INSTANCE}|{2 * MISSES}\n"),
         "step 6, the new container recorded something:\n"
         + subprocess.run(["diff", "-u", "-", ".e2e/lake"], input=again, capture_output=True, text=True).stdout[-2000:])
    until(90, lambda: all(s["licensed"] for s in call(read_datasets)["served"]),
          "step 6, the new container never read its dataset's licence")

    print(f"e2e OK in {int(time.time() - started)}s on the plugin harness: the Ministry's website "
          f"unreachable said on Connection, nothing recorded; sample data's current month to 18 "
          f"November 2026 read, the curve's record asked of the deployment by its code at mof and, "
          f"held by none, reported missing and never minted; read_connection and read_datasets "
          f"answering what the pages show, and core listing {CURVES} as declared; licensed and "
          f"entitled; `store lake` as e2e/expected.lake; and a new container recording nothing, "
          f"its record asked again and its licence read on start")


def main():
    os.makedirs(".e2e", exist_ok=True)
    open(LOG, "w").close()
    try:
        run()
    except (Failed, subprocess.TimeoutExpired, KeyError, ValueError, IndexError, TypeError) as failed:
        with open(COMPONENTS, "a", encoding="utf-8") as kept:
            kept.write(compose("logs", "--no-color", check=False).stdout)
        # The lake as it stood, for the artifact.
        if os.path.exists(".e2e/lake"):
            with open(".e2e/lake", encoding="utf-8") as held, open(".e2e/lake.log", "w", encoding="utf-8") as kept:
                kept.write(held.read())
        compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
        print(f"e2e FAILED: {failed}; the runner's log is in {LOG}, the components' in {COMPONENTS}",
              file=sys.stderr)
        return 1
    compose("--profile", "runner", "down", "-v", "--remove-orphans", check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
