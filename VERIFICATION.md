# Vérification avant publication — 6 octobre 2026

La validation visuelle dans un véritable navigateur reste à faire. La capture utilisateur montre le fond raster sans les couches. Le build précédent ne livrait pas le worker MapLibre v6 à son URL attendue. Cette révision configure explicitement le worker et copie sa dépendance depuis la version installée avant chaque lancement/build.

## Corrections

- Bus et arrêts visibles dès l'ouverture ; nombre de tracés et d'arrêts indiqué dans les contrôles.
- Contour foncé autour des lignes, y compris les lignes blanches du réseau de Laval.
- Fiches accessibles au clic sur les lignes.
- Ventes individuelles visibles au zoom d'ouverture.
- Recentrage après remontage de la carte depuis la recherche ou la page Projets.
- Suppression du point de focus et du détail mobile lors du changement de ville.
- Préservation des identifiants GTFS de Tours contenant des deux-points dans les fréquences par direction.
- Recalcul des comparables lorsque le nombre de pièces du simulateur change ; adresse réinitialisée au changement de ville.

## Vérification automatisée

`node --experimental-strip-types tests/ui.test.mjs`

Les composants TSX réels sont exécutés dans un hôte de hooks de test. Le moteur MapLibre, les contrôles UI, le DOM et le réseau sont simulés. Les snapshots et les fonctions de calcul sont réels. Les styles de toutes les couches sont validés par le validateur MapLibre installé.

Vérifications réussies :

- Laval et Tours : sources GTFS, géométries, huit couches, interrupteurs, clics sur lignes/arrêts/campus/mailles, dessin, rayon, changement de ville, redimensionnement et nettoyage.
- Filtres combinés : pièces, année, budget, frais, rendement et distance.
- Recherche d'adresse avec réponse simulée, enregistrement/restauration des critères, favoris, ajout à la comparaison, CSV, navigation et comparables du simulateur.
- API de géocodage : entrée invalide (400), réponse simulée (200), service indisponible (503).
- Calculs financiers, médianes, géométries avec trous, valeurs manquantes et normalisation DVF : tests existants réussis.

## Vérification encore requise

Dans un navigateur réel, à Laval et à Tours : rendu et chargement des tuiles, activation/désactivation de chaque couche, ordre visuel des couches, interactions entre éléments superposés, recherche IGN réelle, favoris persistants après rechargement, comparaison de quatre secteurs, téléchargement CSV, carte depuis un projet, tous les champs du simulateur, console sans erreur et affichage mobile/desktop.

Les tests automatisés ci-dessus ne certifient pas ces éléments visuels. Aucun screenshot ni contrôle navigateur n'a été réalisé dans cet environnement.

## Worker de production

`node tests/worker.test.mjs` exécute le vrai fichier worker distribué dans un thread séparé, avec les globals hôtes nécessaires. Les fichiers livrés sont comparés octet par octet à la version MapLibre installée. Les sources GTFS lignes/arrêts, communes et points des deux villes produisent effectivement des tuiles GeoJSON non vides. Ce test ne remplace pas un rendu WebGL dans un navigateur.

Le build doit livrer `maplibre-gl-worker.mjs` et `maplibre-gl-shared.mjs` ensemble sous `public/maplibre/`. Le fichier compilé de la carte configure `setWorkerUrl` vers ce chemin.
