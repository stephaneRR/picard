# Backlog — Picard Alt

> Organisé par priorité après brainstorming sessions 1-2. Vérifié par le code.

## Section 1 — Élagage (vérifié par le code, ~7 000 lignes)

### Retraits confirmés
- [ ] Retirer player intégré Qt Multimedia (ui/player/, ~15 refs dans mainwindow — garder PLAY_FILE_EXTERNAL "Ouvrir dans lecteur système")
- [ ] Retirer plugin3 manager/git/CLI/registry (plugin3/manager/, asyncops/, cli.py, installable.py, categories.py — ~3 800 lignes)
- [ ] Retirer module git/ (~1 643 lignes, refs dans plugin3 + tagger.py:144)
- [ ] Garder support plugins v2 (zip/dossier) pour installation manuelle de plugins tiers

### Modules gardés (hypothèses de retrait invalidées par le code)
- Script editor : couplé au renaming (imports directs lignes 58-60 de ui/options/renaming.py) — garder, masquer le bouton "Edit script"
- Profils : profondément intégré dans options/dialog.py (~10 refs) — garder, refaire l'UX
- Session management : utile avec le cache persistant — garder
- CD lookup : utilisé par Stephane — garder

### Intégrations natives
- [ ] Intégrer provider Amazon cover art en natif (⚠️ picard-plugins/plugins/amazon est quasi-vide 0.1KB — code à réécrire ou à retrouver dans l'historique git)
- [ ] Intégrer provider Deezer cover art en natif (picard-plugins/plugins/deezerart, ⚠️ GPL-3.0 — compatible avec notre GPL-2.0-or-later via clause "or later", fichiers intégrés seront sous GPL-3.0)
- [ ] Intégrer provider fanart.tv en natif (picard-plugins/plugins/fanarttv, GPL-2.0)

## Section 2 — Performance (vérifié par le code)

### P1 — Impact fort, prioritaires
- [ ] Cache disque covers par MBID (aucun cache existant — covers en fichiers temp nettoyés au shutdown via DataHash, UI utilise LRUCache(40) en mémoire)
- [ ] Recherche enrichie via Discogs → MB (nouveau : search Discogs 60 req/min, batch URL lookup MB jusqu'à 100 URLs en 1 requête, matching par durées des pistes)
- [ ] Ordre providers cover art : Amazon/Deezer first, CAA en fallback (config ca_providers dans coverart/providers/__init__.py:54-65 — juste changer l'ordre par défaut)
- [ ] Augmenter poids nombre de pistes dans le matching (trackcount_score dans metadata.py:153 — actuellement poids 5/46, scoring asymétrique brutal : 0.0 si plus de fichiers que la release)
- [ ] Auto-vérification versions alternatives si nb pistes ne matche pas (release-group déjà dans le lookup initial, versions loadables via browse)

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
- [ ] Ajouter `is_perfect()` sur Album : `is_complete()` + `is_modified()` + `metadata.images` non vide + pas de tâches critiques
- [ ] Ajouter signal Qt pour la transition vers l'état parfait (pas de signal existant — AlbumItem.update() met à jour l'icône mais n'émet rien)
- [ ] Setting on/off "Auto-save albums when perfectly matched" (désactivé par défaut)
- [ ] Icône existante : `icon_cd_saved_modified` = CD doré (#EBBA16) + étoile pourpre (#800080) — c'est l'état `is_complete() + is_modified()`

### P1 — Meilleure version automatique
- [ ] Après `_finalize_loading_album`, si `get_num_total_files() != len(tracks)` → charger versions automatiquement via `release_group.load_versions()`
- [ ] Chercher la version avec `totaltracks == get_num_total_files()` dans `_alternative_versions`
- [ ] Bouton/notification direct "Version avec X pistes trouvée — Appliquer ?" (pas de clic droit)
- [ ] `switch_release_version(mbid)` existe (album.py:1048) — déplace les fichiers et recharge
- [ ] Ne PAS charger les versions si album déjà parfait (économie de requête)

### P1 — Suppression fichiers indésirables
- [ ] Nouveau setting `delete_junk_files_pattern` avec wildcards (même mécanisme fnmatch que `move_additional_files_pattern`)
- [ ] Envoi à la corbeille via `send2trash` (nouvelle dépendance) au lieu de suppression définitive
- [ ] Remplacer `shutil.rmtree` dans `emptydir.rm_empty_dir()` par `send2trash` aussi (actuellement suppression définitive)
- [ ] Fusionner `JUNK_FILES` (liste en dur : .DS_Store, desktop.ini, Thumbs.db) avec le pattern configurable
- [ ] Appelé dans `_save_and_rename` après déplacement fichiers additionnels, avant `delete_empty_dirs`

### P1 — Recherche enrichie Discogs
- [ ] Transparent pour l'utilisateur — intégré dans le flow de clustering/lookup
- [ ] Setting : token Discogs avec lien direct vers discogs.com/settings/developers
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
