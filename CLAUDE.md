# Picard Alt — Version simplifiée de MusicBrainz Picard

## Projet

Fork de [metabrainz/picard](https://github.com/metabrainz/picard) sous licence GPL-2.0-or-later.
Objectif : créer une version allégée, rapide et simple de MusicBrainz Picard.

## Principes directeurs

- **Simplicité** : moins d'options, moins de complexité, expérience utilisateur fluide
- **Performance** : chargement rapide, illustrations en cache, réactivité de l'interface
- **Pragmatisme** : on retire ce qui ralentit, on garde ce qui est utile au quotidien

## Conventions

- Langue de travail : français pour les échanges, anglais pour le code et les commits
- On ne contribue PAS upstream — c'est un fork indépendant
- Renommage à prévoir (marque "Picard" / "MusicBrainz" appartient à MetaBrainz)

## Structure de travail

- `BACKLOG.md` — idées et fonctionnalités à explorer (pas encore priorisées)
- `SESSION_LOG.md` — journal des sessions de travail
- Mémoire Claude dans le répertoire mémoire du projet

## Stack

- Python, PyQt6
- API MusicBrainz, Discogs, iTunes
- Mutagen (tags audio)
