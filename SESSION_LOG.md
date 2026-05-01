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

### TASK-12 — Garder objet Mutagen du 1er parsing ✅
- 2 commits : cache Mutagen dans tous les formats (210L + 7 tests) + fix memory leak NonCompatID3
- QA passé, cas subtils gérés : mutation tags VComment, incompatibilité ID3 v2.3, APEv2 save différent
- Formats avec réutilisation au save : FLAC, OGG, Opus, MP4, ASF (~200ms économisés/FLAC)
- Formats sans réutilisation (cache nettoyé) : MP3, DSF, AIFF, WAV (ID3 v2.3 incompatible), APEv2
- Sécurité mtime : re-parse si fichier modifié depuis le load
- Cache one-time-use, nettoyé dans finally block
- 4 704 tests passent, 0 échec

### TASK-13 — Séparer indicateurs de progression UI ✅
- 1 commit : 19 lignes modifiées dans infostatus.py
- Les indicateurs étaient déjà séparés (set_pending_files / set_pending_requests)
- Ajouté : séparateur visuel, icônes toggle (grisé quand 0), tooltips descriptifs
- Taskbar progress reste combiné (comportement correct pour l'OS)
- 4 704 tests passent, 0 échec

### TASK-14 — Bug "Dylan:" investigation ✅ (résolu sans code)
- Cause trouvée : plugin **Classical Extras** ligne 1955 de __init__.py
- Code exact : `tm['album'] = "; ".join(new_last_names) + ": " + tm['album']`
- Le plugin préfixe le titre album avec noms de famille des compositeurs (sort-name tronqué)
- "Dylan, Bob" → "Dylan" → "Dylan: Dylan & the Dead"
- Activé par option `cea_composer_album` + relations composer dans MB
- Affecte les pistes individuellement (track metadata processor), pas l'album
- Notre fork n'inclut pas Classical Extras → bug absent

### TASK-15 — Langue sous Windows investigation ✅ (pas de bug)
- L'option de langue est dans Options > User Interface (pas General)
- Redémarrage requis après changement (warning affiché)
- Pas de bug Windows dans le code i18n
- Cause probable : mauvais onglet d'options ou fichiers .mo manquants
- Pour notre fork : compiler les .mo avec `python setup.py build_locales`

## 2026-05-01 — Session 2 (suite) : Review traduction française

### Review complète fr.po ✅
- Fichier : po/fr.po (14 815 lignes, 389 Ko)
- Review parallélisée en 4 agents (sections de ~3 700 lignes chacune)
- Corrections appliquées par 6 agents (2 critiques/grammaire + 4 fuzzy/traductions)
- QA validé : msgfmt --check OK, 0 erreur

### Phase 1 — Corrections critiques + grammaire (37 corrections)
- "Faites ainsi !" → "Exécution !" (Star Trek TNG VF) — 2 endroits
- Accent vietnamien "Ế" → "Ê" — 2 endroits
- "Don't Save" traduit "Enregistrer" (sens opposé !) → "Ne pas enregistrer"
- Raccourci clavier Ctrl+Shift+S → Ctrl+Shift+I (mauvaise correspondance)
- "Personnage" → "Caractère" (contexte remplacement de caractères)
- Caractère parasite supprimé (erreur HTTP)
- "Courriel" (fr-CA) → "E-mail" (fr-FR) — 3 endroits
- "a échouée" → "a échoué" (×6), "Peut être utiliser" → "utilisé" (×7)
- + 15 typos/fautes d'orthographe corrigées

### Phase 2 — Fuzzy absurdes + chaînes non-traduites (~153 corrections)
- 113 entrées fuzzy avec traductions complètement fausses corrigées et dé-fuzzifiées
- 38 chaînes non-traduites critiques traduites (erreurs fichier, plugins, sessions, setup wizard)
- 1 fix msgfmt (variable {filename} dans forme plurielle)
- Statistiques : 913→1060 traduites (+147), 431→323 fuzzy (-108), 372→333 non-traduites (-39)

## 2026-05-01 — Session 2 (suite) : Build portable + audit + options Discogs

### Build portable Windows ✅
- Workflow GitHub Actions `build-portable.yml` créé (workflow_dispatch, Python 3.13)
- picard.spec nettoyé : retiré plugin3 CLI (a_plugins/exe_plugins)
- pyproject.toml : retiré pygit2, picard-plugins CLI entry point
- Fix : `--ignore=test/plugins3` dans pytest du workflow
- Fix : `SettingConfigSection.get()` → accès par `[]` (7 occurrences dans 5 fichiers)
- Build OK, artifact portable .exe uploadé (~59 Mo)

### Audit qualité du code ✅
- ruff lint sur 352 fichiers Python : 0 bug runtime, 24 erreurs de style corrigées dans nos fichiers
- pyright sur nos 14 fichiers modifiés : 0 vrai bug (faux positifs PyQt6/attributs dynamiques)
- ruff + pyright sur tout le codebase par section (3 agents parallèles) : 0 bug runtime
- Nettoyage résidus : pygit2 dans versions.py, pyobjc-framework-MediaPlayer, 3 dossiers fantômes __pycache__

### Page options Discogs ✅
- Nouvelle page Options > Advanced > Discogs (picard/ui/options/discogs.py)
- Checkbox activer/désactiver, champ token, lien cliquable vers discogs.com/settings/developers
- Seuil de matching configurable (spinner 0.0-1.0)
- UI construite programmatiquement (pas de fichier .ui)
- 10 tests synthétiques passent

### Page options Automation ✅
- Nouvelle page Options > Advanced > Automation (picard/ui/options/automation.py)
- Auto-save albums parfaits (checkbox, off par défaut)
- Auto-remove albums après save (checkbox, grisé quand auto-save off)
- Description détaillée du comportement

### Junk files déplacé dans File Naming ✅
- Settings suppression fichiers indésirables déplacés de Automation vers File Naming (renaming.py)
- Regroupé avec "Move additional files" et "Delete empty dirs" — même page, même contexte
- Pattern field grisé quand checkbox off

### Fix status bar jitter ✅
- Labels de compteurs en bas de l'UI passés en largeur fixe (40px)
- Empêche le décalage de l'UI quand les chiffres changent (ex: 9→10→100)

### Simplification tooltip recherche ✅
- "Rechercher les éléments sélectionnés sur MusicBrainz" → "Rechercher les éléments sélectionnés"
- Plus simple et plus exact (Discogs aussi utilisé derrière)

### Auto-remove albums après save ✅
- Nouveau setting auto_remove_saved_albums (off par défaut)
- L'album disparaît de la liste après save réussi (délai 3s + vérification)
- Si erreur de save : album conservé + message d'erreur 10s dans la barre de statut
- Si succès + remove : message "Album saved and removed" 5s
- Messages d'erreur affichés même sans auto-remove activé
- Tous les messages vont dans l'historique (Help > View Activity History, Ctrl+H)

### Fix Deezer cover provider ✅
- "Pas de cover trouvée" n'est plus une erreur — changé en log debug
- Avant : Deezer disait "no results" → album.error_append → icône rouge
- Après : log silencieux, l'album reste doré si la cover vient d'un autre provider
- Vraies erreurs API/réseau toujours signalées en rouge

### Tests synthétiques ✅
- Suite de 15 tests couvrant tous les modules ajoutés/modifiés
- Exécutables sur Mac sans GUI complète
- Cache covers, cache metadata, Discogs matcher, providers, formats, traduction, pytest complet

### Audit sécurité ✅
- pip-audit : 0 CVE dans les dépendances
- bandit : 1 seul finding dans notre code (MD5 pour cache filenames → ajouté usedforsecurity=False)
- 35 findings upstream, tous faux positifs (asserts, try/except/pass, commandes hardcodées)

### Bugs trouvés et corrigés sur le portable Windows
- Fix KeyError "Preset 1" dans l'éditeur de scripts (config fraîche, preset pas encore injecté)
- Fix auto-save ne se déclenchait pas : ajouté trigger sur update_metadata_images (covers = dernière pièce)
- Fix auto-remove après save manuel : chaque fichier notifie l'album après save réussi (_notify_album_save_complete)
- Debug logging ajouté dans _check_auto_save pour diagnostic des conditions

### OAuth MusicBrainz — investigation
- Erreur "Invalid state parameter" sur le portable Windows
- Cause : browser integration (serveur HTTP local) ne fonctionne pas correctement sur le portable
- Le state token est stocké en mémoire dans OAuthManager.__states, vérifié dans browser/server.py:253
- Probable conflit de port ou serveur HTTP local qui ne démarre pas
- Workaround : désactiver Browser Integration dans Options > Advanced > Network → flow OOB (copier-coller code) fonctionne
- Les credentials OAuth Picard (client_id public) sont réutilisables par un fork, pas liés à un redirect_uri spécifique
- Le refresh token est persisté → login ne se fait qu'une fois

### Analyse UI réactivité au chargement (non implémenté, noté)
- _scan_paths_recursive + format_registry.open bloquent le thread UI
- Recommandation : QTimer par lots de ~50 fichiers (~30 lignes, approche A)
- Noté dans le backlog pour implémentation future
