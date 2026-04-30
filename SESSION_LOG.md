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
