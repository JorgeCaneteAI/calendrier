# Fin de vie — calendrier-resas (Flask)

**Date EOL :** 2026-04-27

Ce projet Flask est **remplacé** par une intégration native PHP dans le site
Villa Plaisance (V7), branche `feat/calendrier-integration`, mergée dans `main`
le 2026-04-17.

## Pourquoi

Le calendrier de réservations vit désormais directement dans l'écosystème
Villa Plaisance (PHP, MariaDB, hébergement o2switch) — plus simple à maintenir,
plus performant, intégré au back-office existant.

## Où est le code maintenant

- Repo : `github.com/JorgeCaneteAI/villaplaisance-v7`
- Branche d'origine : `feat/calendrier-integration` (mergée dans `main`)
- Commit de merge : `5345216` — *« merge(calendrier): intégration module
  réservations PHP (remplace Flask) »*

## Pourquoi ce repo reste en ligne

- Référence historique
- Code Flask gardé pour réutilisation éventuelle (autre client, autre projet)
- Permet de revoir la logique iCal de dédupe / les endpoints d'export PDF
