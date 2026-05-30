---
name: jira-workflow-layout
description: >-
  Met à jour la disposition visuelle (positions des nœuds + angles des connecteurs)
  d'un workflow Jira Data Center via l'API interne du Workflow Designer. À utiliser
  quand l'utilisateur veut nettoyer/réorganiser un diagramme de workflow Jira, copier
  la disposition d'un workflow vers un autre, corriger des nœuds/libellés qui se
  chevauchent, ou appliquer une grille propre. Nécessite un Personal Access Token admin Jira.
  Mots-clés : workflow Jira, layout, diagramme, Workflow Designer, mise en page, positions.
---

# Jira workflow layout (Data Center)

Met à jour le **layout** d'un workflow Jira DC sans toucher aux steps/transitions/scripts —
uniquement les positions des nœuds et les angles d'attache des connecteurs.

## Comment ça marche

Le Workflow Designer lit/écrit le layout via une API REST interne :

- **Lecture** : `GET /rest/workflowDesigner/latest/workflows?name=<NAME>&draft=<bool>`
  → `{isDraft, layout:{statuses[], transitions[], loopedTransitionContainer}, workflowPermissions}`
- **Écriture** : `POST /rest/workflowDesigner/latest/workflows`
  body `{"draft":<bool>,"name":<NAME>,"layout":{...}}`
  headers : `Authorization: Bearer <PAT>`, `Content-Type: application/json`, `X-Atlassian-Token: no-check`

Format du `layout` :
- `statuses` : `[{id, x, y}]` — ids stables `S<stepId>` ou `I<1>` (nœud initial).
- `transitions` : `[{id, sourceAngle, targetAngle, sourceId, targetId}]` — id `A<actionId:src:tgt>` ;
  `sourceId`/`targetId` omis pour les transitions bouclées ; angles en degrés (0°=est, 90°=haut).
- `loopedTransitionContainer` : `{x, y}`.

## ⚠️ Entrées à demander à l'utilisateur AVANT toute action

Au démarrage du skill, **toujours demander explicitement** ces informations (ne jamais
les deviner ni réutiliser un ancien token) :

1. **URL du workflow SOURCE** (celui dont on copie la disposition) — l'URL du Workflow
   Designer, ex. `https://jira.example.com/secure/admin/workflows/WorkflowDesigner.jspa?wfName=WF_A&workflowMode=live`.
   *(Inutile pour `grid` qui ne réorganise qu'un seul workflow.)*
2. **URL du workflow CIBLE** (celui qu'on modifie) — même format.
3. **Personal Access Token (PAT) admin** de l'utilisateur.

Le script déduit automatiquement de chaque URL : la **base Jira**, le **nom** du workflow
(`wfName`) et le mode **live/draft** (`workflowMode`). Stocker le PAT dans un fichier temporaire
`chmod 600`, puis le supprimer après usage.

Si une information manque, **la redemander** — ne pas continuer sans les URLs et le token.

## Pré-requis

- **PAT admin** Jira (Profil → Personal Access Tokens).
- Pour `copy` : SOURCE et CIBLE doivent avoir **les mêmes IDs de steps/actions**
  (cas d'une copie de workflow) — sinon les coordonnées ne correspondent pas.

## Utilisation

Le script `scripts/layout_tool.py` (Python 3, sans dépendance) expose 4 sous-commandes.
Toujours **sauvegarder avant de modifier**.

On passe directement les **URLs du Designer** (la base, le nom et live/draft en sont déduits).

```bash
TOOL="python3 ~/.claude/skills/jira-workflow-layout/scripts/layout_tool.py"

# Stocker le PAT fourni par l'utilisateur, sans l'exposer dans les commandes
printf '%s' '<PAT_UTILISATEUR>' > /tmp/jira_tok && chmod 600 /tmp/jira_tok

SRC="https://jira.example.com/secure/admin/workflows/WorkflowDesigner.jspa?wfName=WF_SOURCE&workflowMode=live"
DST="https://jira.example.com/secure/admin/workflows/WorkflowDesigner.jspa?wfName=WF_CIBLE&workflowMode=live"

# 1) Sauvegarde de la CIBLE (rollback) — systématique avant toute modif
$TOOL --token-file /tmp/jira_tok backup --url "$DST" --out /tmp/wf_backup.json

# 2) Copier la disposition SOURCE → CIBLE (IDs identiques requis)
$TOOL --token-file /tmp/jira_tok copy --from-url "$SRC" --to-url "$DST" --apply

# 3) Grille propre auto-calculée sur la CIBLE (best-effort : BFS colonnes,
#    self-loops en éventail, angles recalculés géométriquement)
$TOOL --token-file /tmp/jira_tok grid --url "$DST" --apply

# 4) Appliquer un body layout préparé/édité à la main
$TOOL --token-file /tmp/jira_tok apply --url "$DST" --body /tmp/mon_layout.json

rm -f /tmp/jira_tok   # supprimer le token après usage
```

- Sans `--apply`, `copy`/`grid` font un **dry-run** (utiliser `--out fichier` pour inspecter/éditer le body avant POST).
- `live`/`draft` est déduit de `workflowMode` dans l'URL ; `--draft` force le brouillon.
- Variante sans URL : `--base https://host --name WF` (et `--from/--to` pour `copy`).

### Restauration (rollback)
Le backup (`backup`) contient `{isDraft, layout, ...}`. Pour le ré-appliquer :
```bash
$TOOL --base $BASE --token-file $TOK apply --name "WF_CIBLE" --body /tmp/wf_backup.json
# (la sous-commande apply extrait automatiquement la clé "layout")
```

## Affiner manuellement

Pour un contrôle fin, récupérer le body (`grid --out` ou `copy --out`), éditer dans le JSON :
- `statuses[].x/y` : positions (px ; y plus petit/négatif = plus haut).
- self-loops : régler `sourceAngle`/`targetAngle` (centre = direction de la boucle ; étaler les centres pour déployer plusieurs boucles sur un même nœud).
- connecteurs : `sourceAngle`/`targetAngle` = côté d'attache sur chaque nœud.

Puis `apply --body`. Itérer : appliquer → l'utilisateur recharge le Designer → ajuster.

## Pièges / sécurité

- **WebSudo** : certains endpoints admin exigent une ré-authentification. Si le POST renvoie
  401/403 (entête `X-Atlassian-WebSudo`), exécuter plutôt depuis la **console du navigateur**
  (déjà en session WebSudo) avec le même `fetch`, ou activer WebSudo puis réessayer.
- **Live vs draft** : `draft:false` écrit sur le workflow actif (le layout n'affecte pas l'exécution).
- **Recharger** le Designer (Ctrl/Cmd+R) après un POST pour voir le résultat.
- **Token** : ne pas le committer ni le logger ; supprimer le fichier après usage (`rm -f /tmp/jira_tok`).
- Cette API est **interne/non documentée** par Atlassian → vérifier après une montée de version Jira.

## Alternative sans API

Si l'API n'est pas exploitable : ouvrir le Designer, **glisser les nœuds** manuellement
(l'auto-save du Designer appelle le même endpoint). Le `grid` ou `copy` reste plus rapide pour
reproduire/initialiser une disposition.
