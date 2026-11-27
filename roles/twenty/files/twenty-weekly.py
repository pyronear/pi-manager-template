"""Monday weekly: grant deadlines, organisations to follow up, deployment deals. Posts the report as a Twenty note.
Usage: python3 weekly_report.py [--dry-run]
Config: TWENTY_URL and TWENTY_API_KEY env vars, else a .twenty-login file next to this script.
"""
import json, os, sys, urllib.request
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
if os.environ.get("TWENTY_API_KEY"):
    cfg = {k: os.environ[k] for k in ("TWENTY_URL", "TWENTY_API_KEY")}
else:
    cfg = dict(l.split("=", 1) for l in (HERE / ".twenty-login").read_text().split() if "=" in l)
HORIZON = 14  # days ahead for deadlines / milestones
# days without contact before an organisation shows up as "à relancer", per CRM status (missing = never listed)
STALE_AFTER = {"A_CONTACTER": 14, "A_RELANCER": 14, "O_1ER_CONTACT": 30, "O_1ER_RDV": 30, "EN_DISCUSSION": 30,
               "RECHERCHE_POINTS_HAUTS": 30, "CONTRACTUALISATION": 21, "EN_TEST": 30, "DEPLOIEMENT": 30, "MIS_EN_PLACE": 90}


def call(path, body=None):
    r = urllib.request.Request(cfg["TWENTY_URL"] + "/rest/" + path, data=json.dumps(body).encode() if body else None,
                               headers={"Authorization": "Bearer " + cfg["TWENTY_API_KEY"], "Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(r).read())


def records(obj):
    out, cursor = [], None
    while True:
        d = call(f"{obj}?limit=200" + (f"&starting_after={cursor}" if cursor else ""))
        out += d["data"][obj]
        if not d["pageInfo"]["hasNextPage"]:
            return out
        cursor = d["pageInfo"]["endCursor"]


def labels(obj, field):
    o = next(o for o in call("metadata/objects?limit=200")["data"] if o["nameSingular"] == obj)
    return {x["value"]: x["label"] for x in next(f for f in o["fields"] if f["name"] == field)["options"]}


def d(s):
    return date.fromisoformat(s[:10]) if s else None


def fr(x):
    return x.strftime("%d/%m") if x else "—"


def eur(c):
    return f"{c['amountMicros'] / 1e6:,.0f} €".replace(",", " ") if c and c.get("amountMicros") else ""


today = date.today()
end = today + timedelta(days=HORIZON)
L = [f"Généré le {today.strftime('%d/%m/%Y')} — horizon {HORIZON} jours.", ""]

# --- Subventions
grants = [g for g in records("grants") if g.get("stage") not in ("REFUSEE", "TERMINEE")]
stage = labels("grant", "stage")
items = []
for g in grants:
    for key, what in [("deadline", "Deadline"), ("nextMilestone", "Échéance"), ("answerAt", "Réponse attendue")]:
        x = d(g.get(key))
        if x and x <= end and (x >= today - timedelta(days=7) or key == "nextMilestone"):
            items.append((x, what, g))
L.append("## 💰 Subventions — dates à venir")
if items:
    for x, what, g in sorted(items, key=lambda t: t[0]):
        late = " ⚠️ dépassée" if x < today else ""
        meta = ", ".join(v for v in [stage.get(g.get("stage"), "sans statut"), g.get("internalLead"), eur(g.get("amountRequested"))] if v)
        L.append(f"- **{fr(x)}** — {what}{late} : {g['name']} ({meta})")
else:
    L.append("- Rien dans les 14 prochains jours.")
todo = [g for g in grants if g.get("stage") in (None, "A_ETUDIER", "A_CANDIDATER") and not d(g.get("deadline"))]
if todo:
    L.append(f"- {len(todo)} subvention(s) à étudier ou sans statut, sans deadline : " + ", ".join(g["name"][:40] for g in todo))
L.append("")

# --- Relances CRM
crm = labels("company", "crmStatus")
stale, never = [], []
for c in records("companies"):
    limit = STALE_AFTER.get(c.get("crmStatus"))
    if not c.get("isCrm") or limit is None:
        continue
    last = d(c.get("lastContactAt"))
    if last is None:
        never.append(c)
    elif (today - last).days > limit:
        stale.append(((today - last).days, c))
L.append("## 📞 À relancer")
for days, c in sorted(stale, key=lambda t: -t[0]):
    meta = ", ".join(v for v in [crm.get(c.get("crmStatus")), c.get("leader")] if v)
    L.append(f"- **{c['name'].strip()}** — dernier contact il y a {days} j ({meta})")
if not stale:
    L.append("- Personne en retard de relance 🎉")
if never:
    L.append(f"- Sans aucune date de contact ({len(never)}) : " + ", ".join(c["name"].strip() for c in never))
L.append("")

# --- Déploiements
deals = [o for o in records("opportunities") if o.get("stage") != "EN_SERVICE"]
dstage = labels("opportunity", "stage")
L.append("## 📡 Déploiements en cours")
for o in sorted(deals, key=lambda o: o.get("closeDate") or "9999"):
    prog = f"{o.get('stationsLive') or 0}/{o['stationsPlanned']} stations" if o.get("stationsPlanned") else ""
    meta = ", ".join(v for v in [dstage.get(o.get("stage")), prog, ("cible " + fr(d(o.get("closeDate")))) if o.get("closeDate") else ""] if v)
    L.append(f"- {o['name']} ({meta})")
if not deals:
    L.append("- Aucun deal en cours.")

L.append("")

# --- Tâches
members = {m["id"]: f"{m['name']['firstName']} {m['name']['lastName']}".strip() for m in records("workspaceMembers")}
tasks = records("tasks")
who = lambda t: members.get(t.get("assigneeId"), "non assignée")
late = [t for t in tasks if t.get("status") != "DONE" and d(t.get("dueAt")) and d(t.get("dueAt")) < today]
soon = [t for t in tasks if t.get("status") != "DONE" and d(t.get("dueAt")) and today <= d(t.get("dueAt")) <= today + timedelta(days=7)]
done = [t for t in tasks if t.get("status") == "DONE" and d(t.get("updatedAt")) and d(t.get("updatedAt")) >= today - timedelta(days=7)]
L.append("## ✅ Tâches")
for label, group in [("⚠️ En retard", late), ("Cette semaine", soon)]:
    for t in sorted(group, key=lambda t: t["dueAt"]):
        L.append(f"- {label} — **{fr(d(t['dueAt']))}** : {t.get('title') or '(sans titre)'} ({who(t)})")
if done:
    L.append(f"- Faites cette semaine ({len(done)}) : " + ", ".join(f"{t.get('title') or '(sans titre)'} ({who(t)})" for t in done))
if not (late or soon or done):
    L.append("- Aucune tâche en retard, à venir ou faite cette semaine.")

title = f"Weekly du {today.strftime('%d/%m/%Y')}"
md = "\n".join(L)
print(title, "\n\n" + md)
if "--dry-run" not in sys.argv:
    call("notes", {"title": title, "bodyV2": {"markdown": md}})
    print("\n→ note créée dans Twenty")
