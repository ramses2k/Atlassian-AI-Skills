#!/usr/bin/env python3
"""
Outil de gestion du LAYOUT (positions des nœuds + angles des connecteurs) d'un
workflow Jira Data Center, via l'API interne du Workflow Designer.

Endpoints (Jira DC, plugin jira-workflow-designer) :
  GET  /rest/workflowDesigner/latest/workflows?name=<NAME>&draft=<bool>
  POST /rest/workflowDesigner/latest/workflows
       body = {"draft":<bool>, "name":<NAME>, "layout":{statuses, transitions, loopedTransitionContainer}}
       headers : Authorization: Bearer <PAT>, Content-Type: application/json, X-Atlassian-Token: no-check

Aucune dépendance externe (urllib uniquement).
"""
import argparse, json, sys, math, urllib.request, urllib.error, urllib.parse


# ─────────────────────────────────────────────────────────────
# HTTP
# ─────────────────────────────────────────────────────────────
def _http(base, path, token, method="GET", body=None, timeout=30):
    url = base.rstrip("/") + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/json")
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Atlassian-Token", "no-check")  # anti-CSRF Jira
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def parse_designer_url(url):
    """Extrait (base, name, draft) depuis une URL du Workflow Designer, ex.
    https://host/secure/admin/workflows/WorkflowDesigner.jspa?wfName=NAME&workflowMode=live
    Accepte aussi une simple base (https://host) → (base, None, None)."""
    u = urllib.parse.urlparse(url)
    base = f"{u.scheme}://{u.netloc}"
    qs = urllib.parse.parse_qs(u.query)
    name = (qs.get("wfName") or qs.get("name") or [None])[0]
    mode = (qs.get("workflowMode") or [None])[0]
    draft = None if mode is None else (mode.lower() == "draft")
    return base, name, draft


def get_workflow(base, token, name, draft=False):
    q = urllib.parse.urlencode({"name": name, "draft": str(draft).lower()})
    st, body = _http(base, f"/rest/workflowDesigner/latest/workflows?{q}", token)
    if st != 200:
        sys.exit(f"[ERREUR] GET workflow '{name}' → HTTP {st}\n{body[:400]}")
    return json.loads(body)


def apply_layout(base, token, name, layout, draft=False):
    body = {"draft": draft, "name": name, "layout": layout}
    st, resp = _http(base, "/rest/workflowDesigner/latest/workflows", token, "POST", body)
    return st, resp


# ─────────────────────────────────────────────────────────────
# Sérialisation layout (reproduit le WorkflowDataWriter du Designer)
# ─────────────────────────────────────────────────────────────
def writer_layout(layout):
    statuses = [{"id": s["id"], "x": s["x"], "y": s["y"]} for s in layout["statuses"]]
    transitions = []
    for t in layout["transitions"]:
        o = {"id": t["id"], "sourceAngle": t.get("sourceAngle"), "targetAngle": t.get("targetAngle")}
        if not t.get("loopedTransition"):
            o["sourceId"] = t.get("sourceId")
            o["targetId"] = t.get("targetId")
        transitions.append(o)
    out = {"statuses": statuses, "transitions": transitions}
    c = layout.get("loopedTransitionContainer")
    if c:
        out["loopedTransitionContainer"] = {"x": c["x"], "y": c["y"]}
    return out


# ─────────────────────────────────────────────────────────────
# Auto-layout "grille" (best-effort)
# ─────────────────────────────────────────────────────────────
def _norm(a):
    while a > 180: a -= 360
    while a <= -180: a += 360
    return a


def grid_layout(layout, col_dx=440, row_dy=260, x0=120, y0=140, nw=170, nh=50):
    statuses = layout["statuses"]
    by_id = {s["id"]: s for s in statuses}
    # adjacence via transitions normales (statut→statut, non-self, non-global)
    adj = {s["id"]: [] for s in statuses}
    for t in layout["transitions"]:
        if t.get("globalTransition") or t.get("loopedTransition"):
            continue
        s, tg = t.get("sourceId"), t.get("targetId")
        if s in by_id and tg in by_id and s != tg:
            adj[s].append(tg)
    # nœud initial : id "I<...>" sinon premier
    initial = next((s["id"] for s in statuses if s["id"].startswith("I<")), statuses[0]["id"])
    # BFS → profondeur (colonne) = distance min depuis l'initial
    depth = {initial: 0}
    queue = [initial]
    while queue:
        n = queue.pop(0)
        for m in adj[n]:
            if m not in depth or depth[m] > depth[n] + 1:
                depth[m] = depth[n] + 1
                queue.append(m)
    maxd = max(depth.values()) if depth else 0
    for s in statuses:                       # nœuds non atteints → dernière colonne
        depth.setdefault(s["id"], maxd + 1)
    # rangs dans chaque colonne
    cols = {}
    for s in statuses:
        cols.setdefault(depth[s["id"]], []).append(s["id"])
    pos = {}
    for col, ids in cols.items():
        for row, sid in enumerate(ids):
            pos[sid] = (x0 + col * col_dx, y0 + row * row_dy)

    def center(sid):
        x, y = pos[sid]; return (x + nw / 2, y + nh / 2)

    def ang(s, tg):
        sx, sy = center(s); tx, ty = center(tg)
        return math.degrees(math.atan2(sy - ty, tx - sx))   # 0=est, 90=haut

    # self-loops fan-out (par nœud, sur le haut)
    selfcnt = {}
    for t in layout["transitions"]:
        if (not t.get("globalTransition")) and t.get("sourceId") == t.get("targetId"):
            selfcnt[t["sourceId"]] = selfcnt.get(t["sourceId"], 0) + 1
    fan = {}
    for sid, n in selfcnt.items():
        if n == 1:
            fan[sid] = [90.0]
        else:
            fan[sid] = [35 + (110 * i / (n - 1)) for i in range(n)]   # 35°→145°
    fan_idx = {k: 0 for k in fan}

    new_statuses = [{"id": sid, "x": float(pos[sid][0]), "y": float(pos[sid][1])} for sid in pos]
    new_trans = []
    for t in layout["transitions"]:
        o = {"id": t["id"]}
        s, tg = t.get("sourceId"), t.get("targetId")
        if t.get("globalTransition") or t.get("loopedTransition"):
            o["sourceAngle"] = t.get("sourceAngle"); o["targetAngle"] = t.get("targetAngle")
            if not t.get("loopedTransition"):
                o["sourceId"] = s; o["targetId"] = tg
        elif s == tg and s in fan:
            c = fan[s][fan_idx[s]]; fan_idx[s] += 1
            o["sourceAngle"] = _norm(c - 15); o["targetAngle"] = _norm(c + 15)
            o["sourceId"] = s; o["targetId"] = tg
        else:
            a = ang(s, tg)
            o["sourceAngle"] = _norm(a); o["targetAngle"] = _norm(a + 180)
            o["sourceId"] = s; o["targetId"] = tg
        new_trans.append(o)
    out = {"statuses": new_statuses, "transitions": new_trans}
    c = layout.get("loopedTransitionContainer")
    out["loopedTransitionContainer"] = {"x": c["x"], "y": c["y"]} if c else {"x": 0.0, "y": 0.0}
    return out


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def _read_token(args):
    if args.token:
        return args.token.strip()
    if args.token_file:
        return open(args.token_file).read().strip()
    sys.exit("[ERREUR] Fournir --token ou --token-file (PAT admin Jira).")


def _resolve(base, url, name, draft):
    """Combine --url (URL Designer) et/ou --base/--name/--draft. L'URL prime."""
    if url:
        b, n, d = parse_designer_url(url)
        base = base or b
        name = name or n
        if d is not None:
            draft = d
    if not base:
        sys.exit("[ERREUR] Base Jira manquante : fournir --url <URL Designer> ou --base <https://host>.")
    if not name:
        sys.exit("[ERREUR] Nom du workflow manquant : --url (avec wfName) ou --name.")
    return base, name, bool(draft)


def main():
    p = argparse.ArgumentParser(description="Layout d'un workflow Jira DC via l'API Workflow Designer")
    p.add_argument("--base", help="URL Jira, ex. https://jira.example.com (sinon déduite de --url)")
    p.add_argument("--token", help="Personal Access Token admin")
    p.add_argument("--token-file", help="Fichier contenant le PAT (préféré)")
    p.add_argument("--draft", action="store_true", help="Forcer la cible brouillon (sinon déduit de l'URL / live)")
    sub = p.add_subparsers(dest="cmd", required=True)

    sb = sub.add_parser("backup", help="Sauvegarder le layout d'un workflow")
    sb.add_argument("--url", help="URL Designer du workflow")
    sb.add_argument("--name"); sb.add_argument("--out", required=True)

    sc = sub.add_parser("copy", help="Copier le layout d'un workflow vers un autre (IDs identiques requis)")
    sc.add_argument("--from-url", dest="src_url", help="URL Designer du workflow SOURCE")
    sc.add_argument("--to-url", dest="dst_url", help="URL Designer du workflow CIBLE")
    sc.add_argument("--from", dest="src", help="Nom du workflow SOURCE")
    sc.add_argument("--to", dest="dst", help="Nom du workflow CIBLE")
    sc.add_argument("--apply", action="store_true", help="POSTer (sinon dry-run)")
    sc.add_argument("--out", help="Fichier où écrire le body généré")

    sg = sub.add_parser("grid", help="Calculer un layout grille propre et l'appliquer")
    sg.add_argument("--url", help="URL Designer du workflow")
    sg.add_argument("--name"); sg.add_argument("--apply", action="store_true")
    sg.add_argument("--out", help="Fichier où écrire le body généré")

    sa = sub.add_parser("apply", help="Appliquer un body layout déjà préparé (JSON)")
    sa.add_argument("--url", help="URL Designer du workflow")
    sa.add_argument("--name"); sa.add_argument("--body", required=True)

    args = p.parse_args()
    token = _read_token(args)

    if args.cmd == "backup":
        base, name, draft = _resolve(args.base, args.url, args.name, args.draft)
        wf = get_workflow(base, token, name, draft)
        json.dump(wf, open(args.out, "w"), ensure_ascii=False, indent=2)
        print(f"[OK] Layout de '{name}' sauvegardé → {args.out}")

    elif args.cmd == "copy":
        sbase, sname, sdraft = _resolve(args.base, args.src_url, args.src, args.draft)
        dbase, dname, ddraft = _resolve(args.base, args.dst_url, args.dst, args.draft)
        src = get_workflow(sbase, token, sname, sdraft)
        layout = writer_layout(src["layout"])
        body = {"draft": ddraft, "name": dname, "layout": layout}
        if args.out:
            json.dump(body, open(args.out, "w"), ensure_ascii=False)
            print(f"[OK] Body écrit → {args.out}")
        if args.apply:
            st, resp = apply_layout(dbase, token, dname, layout, ddraft)
            print(f"[{'OK' if st in (200,204) else 'ERREUR'}] POST '{dname}' → HTTP {st} {resp[:200]}")
        else:
            print(f"[DRY-RUN] Ajouter --apply pour POSTer. {sname} → {dname} : "
                  f"{len(layout['statuses'])} statuts, {len(layout['transitions'])} transitions.")

    elif args.cmd == "grid":
        base, name, draft = _resolve(args.base, args.url, args.name, args.draft)
        wf = get_workflow(base, token, name, draft)
        layout = grid_layout(wf["layout"])
        body = {"draft": draft, "name": name, "layout": layout}
        if args.out:
            json.dump(body, open(args.out, "w"), ensure_ascii=False)
            print(f"[OK] Body écrit → {args.out}")
        if args.apply:
            st, resp = apply_layout(base, token, name, layout, draft)
            print(f"[{'OK' if st in (200,204) else 'ERREUR'}] POST '{name}' → HTTP {st} {resp[:200]}")
        else:
            print("[DRY-RUN] Ajouter --apply pour POSTer.")

    elif args.cmd == "apply":
        base, name, draft = _resolve(args.base, args.url, args.name, args.draft)
        body = json.load(open(args.body))
        layout = body["layout"] if "layout" in body else body
        st, resp = apply_layout(base, token, name, layout, draft)
        print(f"[{'OK' if st in (200,204) else 'ERREUR'}] POST '{name}' → HTTP {st} {resp[:200]}")


if __name__ == "__main__":
    main()
