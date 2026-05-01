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
- [ ] Cache persistant metadata MB avec bouton "Vider le cache" (base existante dans _mb_cache de session_loader.py:577)
- [ ] Pré-chargement versions release-group dès le lookup initial (au lieu d'attendre le clic droit — basetreeview.py:160-174)
- [ ] Garder l'objet Mutagen du parsing initial pour la sauvegarde (évite double parsing — gain ~200ms/FLAC, ~50ms/MP3 — stocker en attribut de File, vérifier mtime avant réutilisation)
- [ ] Ne pas ré-embedder la cover si identique au save précédent

### P3 — Gains complémentaires
- [ ] Configurer délais rate limiting plus bas pour sources non-MB (mécanisme déjà par host dans ratecontrol.py:82 — juste configuration)
- [ ] Séparer visuellement dans l'UI "requêtes réseau en cours" vs "fichiers en attente de sauvegarde" (statusindicator additionne pending_files + pending_requests)

### Non retenu
- ~~Écriture fichiers parallèle~~ : save_thread_pool volontairement limité à 1 thread (tagger.py:322-324) pour éviter race conditions sur renommage/déplacement
- ~~Maximiser les inc= parameters~~ : déjà fait, album.py:807-844 demande le maximum
- ~~Batch API MusicBrainz~~ : impossible, API ne supporte que 1 entité par requête (sauf URL lookup)

## Section 2 — Bugs identifiés
- [ ] Bug "Dylan:" — sort-name tronqué préfixé au titre album sur releases multi-artistes (docs/picard_bug_report.docx, cause probable dans translate_from_sortname picard/util/__init__.py + _translate_artist_node mbjson.py:543)
- [ ] Investiguer changement de langue sous Windows (i18n.py, GetUserDefaultUILanguage)

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
- [ ] Setting : token Discogs avec lien direct vers discogs.com/settings/developers (UI à ajouter)
- [ ] Tooltip album : "Identifié via Discogs + MusicBrainz" quand Discogs a enrichi le résultat

## Simplification UI — Approche progressive
> Principe : ajouter d'abord nos features dans l'UI existante, utiliser le produit, puis créer une
> vue simplifiée qui masque les éléments non essentiels (setVisible(false)) sans détruire la vue experte.

### Phase 1 — Additive (ajouter nos features)
- [ ] Toutes les features ci-dessus dans l'UI actuelle
- [ ] Séparer indicateurs : "requêtes réseau" vs "fichiers en attente de sauvegarde"
- [ ] Nouveau setting pour la liste de fichiers à envoyer à la corbeille (wildcards)

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
