# Session Log — Picard Alt

## 2026-04-30 — Session 1 : Initialisation

- Fork créé : https://github.com/stephaneRR/picard
- Repo cloné localement
- Indexation du codebase lancée (claude-context)
- Structure de travail initialisée (CLAUDE.md, BACKLOG.md, SESSION_LOG.md)
- Vision initiale : version simplifiée et performante de Picard
- Pas encore de décisions techniques — phase d'exploration

## 2026-04-30 — Session 1 (suite) : Brainstorming & Design

### Décisions prises
- Approche "Picard Hybrid" : Phase 1 élagage/perf, Phase 2 éventuelle refonte UI
- Rester en Python + PyQt (pas de réécriture C/Rust)
- Intégrer Amazon, Deezer, fanart.tv en natif (cover art providers)
- Garder support plugins v2 (zip/dossier) pour pouvoir ajouter des plugins tiers
- Retirer plugin3 manager/git/CLI/registry (~3 800 lignes)
- Retirer player intégré Qt Multimedia (~1 500 lignes, garder "Ouvrir dans lecteur système")
- Retirer module git/ (~1 643 lignes)
- Garder script editor (couplé au renaming — hypothèse de retrait invalidée par le code)
- Garder profils (profondément intégré dans options/dialog.py)
- Garder CD lookup, session management, remotecommands

### Bug "Dylan:" identifié
- Sort-name tronqué préfixé au titre album sur releases multi-artistes
- Fichiers de référence dans docs/ (JSON + docx)
- Cause probable : mécanisme translate_from_sortname dans picard/util/__init__.py

### Leçon
- Vérification systématique du code avant chaque hypothèse de retrait
- Gain réel estimé : ~7 000 lignes (vs 14 500 initialement estimé)

## 2026-04-30 — Session 1 (suite) : Section 2 Performance

### Analyse API MusicBrainz
- Pas de batch API (1 entité par requête, sauf URL lookup jusqu'à 100 URLs)
- Rate limit strict : 1 req/s vers musicbrainz.org
- Le lookup album récupère déjà toutes les pistes en 1 requête (inc= déjà maximisé)
- Le fingerprinting (AcoustID) fait des lookups recordings séquentiels (1 par recording MBID)

### Recherche enrichie via Discogs (feature différenciante)
- API Discogs : search par artiste/album, 60 req/min authentifié (token simple)
- Flow : Discogs search → enrichir avec barcode/catno/titre exact → MB lookup précis
- Batch URL lookup MB : passer jusqu'à 100 URLs Discogs en 1 requête pour récupérer les MBIDs
- Matching par durées des pistes (signal le plus fiable, indépendant de la langue et de l'ordre)

### Covers art
- Aucun cache disque existant (DataHash crée des fichiers temp nettoyés au shutdown)
- Providers sont séquentiels par album mais le webservice est déjà multi-host
- CAA (archive.org) instable — confirmé par Stephane : au bout d'un moment les covers ne chargent plus
- Décision : Amazon/Deezer en premier, CAA en fallback (juste changer ca_providers)

### Matching nombre de pistes
- trackcount_score est brutal : 0.0 si plus de fichiers que la release, 0.3 si moins
- Poids du nombre de pistes : seulement 5/46 dans CLUSTER_COMPARISON_WEIGHTS
- Cause directe du problème "mauvaise version sélectionnée" → augmenter le poids

### Écriture des fichiers
- save_thread_pool limité à 1 thread intentionnellement (race conditions)
- L'écriture ne bloque pas le réseau MAIS bloque la finalisation d'autres albums (état PENDING)
- Le timer UI additionne pending_files + pending_requests → impression de lenteur globale
- Double parsing Mutagen : le fichier est parsé au chargement puis re-parsé à la sauvegarde
- L'objet Mutagen du 1er parsing n'est pas conservé → peut être stocké comme attribut de File
- Gain estimé : ~200ms/FLAC, ~50ms/MP3 en évitant le double parsing
- FLAC plus lent que MP3 car réécriture complète du fichier (pas de padding comme ID3)
- Mutagen est à jour (1.47.0, dernière version PyPI sept 2023)

## 2026-04-30 — Session 1 (suite) : Section 3 Nouvelles fonctionnalités

### Auto-save albums parfaits
- Icône CD doré + étoile = `is_complete() + is_modified()` dans AlbumItem.update()
- `is_complete()` vérifie tracks matchées mais PAS la cover → ajouter check images
- Pas de signal Qt existant pour la transition → à créer
- `iter_correctly_matched_tracks` et `save_matched` existent comme base

### Meilleure version automatique
- `switch_release_version(mbid)` existe et fonctionne
- `_alternative_versions` trie déjà par nb pistes matching
- Charger versions seulement si album imparfait (nb fichiers != nb pistes)
- Bouton direct au lieu de clic droit

### Suppression fichiers indésirables
- Pattern wildcards via fnmatch — même mécanisme que move_additional_files
- Actuellement `shutil.rmtree` = suppression définitive, pas corbeille
- `JUNK_FILES` en dur (.DS_Store, desktop.ini, Thumbs.db) → rendre configurable
- Utiliser `send2trash` (nouvelle dépendance) pour corbeille cross-platform

### Simplification UI — Approche progressive
- Décision : ne pas casser l'UI existante
- Phase 1 : ajouter nos features dans l'UI actuelle, utiliser le produit
- Phase 2 : vue simplifiée switchable (setVisible(false)) basée sur l'usage réel
- Garder la vue experte accessible en dessous

## 2026-05-01 — Session 2 : Implémentation

### Environnement de dev
- uv installé (Homebrew v0.11.8)
- Venv Python 3.13.13 créé (Python 3.14 du système incompatible avec pip)
- pytest installé, 4 618 tests passent

### TASK-01 — Retirer player intégré ✅
- 3 commits : retrait principal (2 188 lignes), nettoyage options orphelines, nettoyage test
- QA passé : tous imports vérifiés, PLAY_FILE_EXTERNAL intact
- 4 618 tests passent, 0 échec

### TASK-02 — Retirer plugin3 manager/git/CLI ✅
- 2 commits : retrait principal (9 742 lignes, 40 fichiers), fix tests (548 lignes supprimées)
- Nouveau PluginManager local minimal (264 lignes) remplace le manager git-based
- Extension points intacts, API plugin intacte
- Fix : config key alignée (plugins3_enabled_plugins), enable_plugin compatible mock, QObject parent
- 4 595 tests passent, 0 échec

### TASK-03 — Intégrer providers Amazon/Deezer/fanart.tv en natif ✅
- 1 commit : 642 lignes ajoutées (amazon.py 139L, deezer.py 337L, fanarttv.py 147L)
- QA passé : 11/11 checks OK, code vérifié contre les plugins originaux fournis par Stephane
- Amazon : fidèle au plugin original (ASIN, serveurs régionaux, match_url_relations)
- Deezer : inliné depuis 3 fichiers, adapté PyQt5→PyQt6, GPL-3.0 compatible
- fanart.tv : API key publique, release group ID, cd art
- Ordre par défaut : Amazon, Deezer, fanart.tv, CAA, CaaReleaseGroup
- 4 595 tests passent, 0 échec

### TASK-04 — Cache disque persistant pour cover arts ✅
- 2 commits : cache module (521 lignes + 14 tests) + fix éviction automatique dans put()
- QA : 9/9 checks OK, 1 fix appliqué (éviction manquante dans put())
- Cache dans QStandardPaths.CacheLocation/covers/{mbid}/, thread-safe, TTL par mtime
- Intégré dans _handle_queued_image (check avant download) et _coverart_downloaded (save après)
- 4 609 tests passent, 0 échec

### TASK-05 — Recherche enrichie via Discogs ✅
- 2 commits : implémentation (975 lignes, 39 tests) + fix QA (3 issues corrigées)
- QA : 10 checks, 1 bug critique corrigé (parsing réponse MB URL — données nestées sous 'url')
- Fix : guard _discogs_lookup_active contre lookups concurrents, docstring lookup_urls
- Flow : Discogs search → top 3 → fetch tracklist → matching durées → MB URL lookup → load album
- Nouveau package picard/matching/ avec discogs_matcher.py
- Nouveau picard/webservice/api_helpers/discogs.py
- Settings : discogs_enabled, discogs_token, discogs_match_threshold
- 4 648 tests passent, 0 échec

### TASK-06 — Augmenter poids totalalbumtracks de 5 à 10 ✅
- 1 commit : 1 ligne changée dans cluster.py
- Benchmark sur 1000 cas (60% easy, 25% medium, 15% hard) : first match 92.5% → 94.2%
- +28 améliorations (100% exact edition match), -11 régressions (100% albums incomplets, fixables par TASK-05/07)
- 0 régression non-fixable
- 4 648 tests passent, 0 échec

### TASK-07 — Auto-vérification versions alternatives ✅
- 1 commit : 53 lignes ajoutées dans album.py, 11 tests
- QA passé : 7/7 checks OK, 0 issue, code purement additif
- Après _finalize_loading_album, si nb fichiers != nb pistes → charge les versions du release-group
- Cherche version avec totaltracks == nb fichiers, notifie via statusbar (pas d'auto-switch)
- 4 659 tests passent, 0 échec

### TASK-08 — Auto-save des albums parfaits ✅
- 1 commit : 64 lignes album.py + 262 lignes tests (20 tests)
- QA passé : 8/8 checks OK, 0 issue, edge cases couverts
- is_perfect() = loaded + is_complete + is_modified + images + no tasks
- Délai 2s via QTimer, re-check avant save, pas de double-scheduling
- Appelé depuis _finalize_loading_album() et complete_task()
- Utilise file.save() = pipeline complet (tags + rename + move + cleanup)
- Setting auto_save_perfect_albums = False par défaut
- 4 679 tests passent, 0 échec

### TASK-09 — Suppression fichiers indésirables → corbeille ✅
- 1 commit : _delete_junk_files dans file.py + emptydir.py send2trash + 9 tests
- QA passé : 8/8 checks OK
- Pattern configurable (*.url *.nfo *.m3u *.txt *.log par défaut), même syntaxe fnmatch
- send2trash pour corbeille, fallback os.remove si indisponible
- emptydir.py : shutil.rmtree remplacé par send2trash
- Appelé dans _save_and_rename après move_additional_files, avant delete_empty_dirs
- Protection : fichiers chargés dans Picard jamais supprimés
- Setting delete_junk_files = False par défaut (opt-in)
- 4 688 tests passent, 0 échec

### TASK-10 — Cache persistant metadata MusicBrainz ✅
- 2 commits : cache module (156L + 9 tests) + fix écriture redondante sur cache hit
- QA : 7 checks OK, 1 fix appliqué (skip cache.put quand données viennent du cache)
- Cache JSON par MBID dans QStandardPaths.CacheLocation/metadata/
- TTL 7 jours par défaut, thread-safe, _CACHE_HIT_SENTINEL pour bypass load_request guard
- Intégré dans album.load() (check avant API) et _release_request_finished (save après succès)
- refresh=True bypass le cache, erreurs jamais cachées
- Settings metadata_cache_enabled=True, metadata_cache_ttl_days=7
- 4 697 tests passent, 0 échec
