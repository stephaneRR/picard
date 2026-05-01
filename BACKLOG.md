# Backlog — Picard Alt

> Organisé par priorité après brainstorming sessions 1-2. Vérifié par le code.

## Section 1 — Élagage (vérifié par le code, ~7 000 lignes)

### Retraits confirmés
- [x] Retirer player intégré Qt Multimedia ✅ TASK-01 — 2 188 lignes, 3 commits, 4 618 tests OK
- [x] Retirer plugin3 manager/git/CLI + module git/ ✅ TASK-02 — 10 290 lignes, 2 commits, 4 595 tests OK
- [x] Garder support plugins v2 (zip/dossier) pour installation manuelle de plugins tiers ✅ PluginManager local créé

### Modules gardés (hypothèses de retrait invalidées par le code)
- Script editor : couplé au renaming (imports directs lignes 58-60 de ui/options/renaming.py) — garder, masquer le bouton "Edit script"
- Profils : profondément intégré dans options/dialog.py (~10 refs) — garder, refaire l'UX
- Session management : utile avec le cache persistant — garder
- CD lookup : utilisé par Stephane — garder

### Intégrations natives
- [x] Intégrer provider Amazon cover art en natif ✅ TASK-03 — depuis plugin original fourni par Stephane
- [x] Intégrer provider Deezer cover art en natif ✅ TASK-03 — GPL-3.0 compatible, inliné depuis 3 fichiers
- [x] Intégrer provider fanart.tv en natif ✅ TASK-03 — API key publique, release group ID

## Section 2 — Performance (vérifié par le code)

### P1 — Impact fort, prioritaires
- [x] Cache disque covers par MBID ✅ TASK-04 — cache.py 287L + 14 tests, TTL + LRU eviction, thread-safe
- [x] Recherche enrichie via Discogs → MB ✅ TASK-05 — 975L + 39 tests, matching durées, flow Discogs→MB URL lookup
- [x] Ordre providers cover art : Amazon/Deezer first, CAA en fallback ✅ TASK-03 — intégré dans DEFAULT_CA_PROVIDERS
- [x] Augmenter poids nombre de pistes dans le matching ✅ TASK-06 — poids 5→10, benchmarké sur 1000 cas, +28 améliorations, 0 régression non-fixable
- [x] Auto-vérification versions alternatives si nb pistes ne matche pas ✅ TASK-07 — notification statusbar, 11 tests

### P2 — Impact moyen, bons gains
- [x] Cache persistant metadata MB ✅ TASK-10 — JSON par MBID, TTL 7j, 9 tests
- [ ] Pré-chargement versions release-group dès le lookup initial (au lieu d'attendre le clic droit — basetreeview.py:160-174)
- [x] Garder objet Mutagen du parsing initial ✅ TASK-12 — gain ~200ms/FLAC, mtime check, 7 tests
- [ ] Ne pas ré-embedder la cover si identique au save précédent

### P3 — Gains complémentaires
- [ ] Configurer délais rate limiting plus bas pour sources non-MB (mécanisme déjà par host dans ratecontrol.py:82 — juste configuration)
- [x] Séparer visuellement dans l'UI réseau vs sauvegarde ✅ TASK-13 — séparateur, tooltips, icônes toggle

### Non retenu
- ~~Écriture fichiers parallèle~~ : save_thread_pool volontairement limité à 1 thread (tagger.py:322-324) pour éviter race conditions sur renommage/déplacement
- ~~Maximiser les inc= parameters~~ : déjà fait, album.py:807-844 demande le maximum
- ~~Batch API MusicBrainz~~ : impossible, API ne supporte que 1 entité par requête (sauf URL lookup)

## Section 2 — Bugs identifiés
- [x] Bug "Dylan:" ✅ TASK-14 — Cause : plugin Classical Extras ligne 1955 (cea_composer_album). Absent de notre fork.
- [x] Langue Windows ✅ TASK-15 — Pas de bug, option dans User Interface, compiler .mo pour le build

## Section 3 — Nouvelles fonctionnalités (vérifié par le code)

### P1 — Auto-save albums parfaits
- [x] is_perfect() + _check_auto_save + _auto_save_execute ✅ TASK-08 — 20 tests, délai 2s, setting off par défaut

### P1 — Meilleure version automatique
- [x] Auto-vérification versions + notification statusbar ✅ TASK-07 — 11 tests
- [ ] `switch_release_version(mbid)` existe (album.py:1048) — déplace les fichiers et recharge
- [ ] Ne PAS charger les versions si album déjà parfait (économie de requête)

### P1 — Suppression fichiers indésirables
- [x] Suppression fichiers indésirables → corbeille ✅ TASK-09 — send2trash, pattern configurable, 9 tests

### P1 — Recherche enrichie Discogs
- [x] Intégré dans le flow de clustering/lookup ✅ TASK-05
- [x] Setting : token Discogs avec lien direct vers discogs.com/settings/developers ✅ — Options > Advanced > Discogs
- [ ] Tooltip album : "Identifié via Discogs + MusicBrainz" quand Discogs a enrichi le résultat

## Simplification UI — Approche progressive
> Principe : ajouter d'abord nos features dans l'UI existante, utiliser le produit, puis créer une
> vue simplifiée qui masque les éléments non essentiels (setVisible(false)) sans détruire la vue experte.

### Phase 1 — Additive (ajouter nos features)
- [x] Toutes les features dans l'UI actuelle ✅ — Pages options Discogs, Automation, junk files dans File Naming
- [x] Séparer indicateurs : "requêtes réseau" vs "fichiers en attente de sauvegarde" ✅ TASK-13
- [x] Nouveau setting pour la liste de fichiers à envoyer à la corbeille (wildcards) ✅ — Options > File Naming

### Phase 2 — Vue simplifiée (après usage réel)
- [ ] Toggle "Mode simple / Mode expert" (menu ou premier lancement)
- [ ] Masquer panneaux/options non essentiels via setVisible(false)
- [ ] Réduire 31 pages d'options → ~8-10 pages regroupées
- [ ] Masquer bouton "Edit script" dans renaming
- [ ] Simplifier UX des profils
- [ ] Décisions basées sur l'usage réel, pas sur des hypothèses

## Phase 2 — Identité & UX (plus tard)
- [ ] Renommer le fork (nom, icône, about)
- [ ] Adapter les métadonnées (setup.py, manifestes, etc.)
- [ ] Détection de doublons intégrée (remplacer dupeguru — par musicbrainz_recordingid)
