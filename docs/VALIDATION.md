# Validation locale — 7 octobre 2026

Le serveur de production fonctionne à `http://127.0.0.1:3000`. Le Site public n'a pas été republié. Son identifiant reste `appgprj_6ac54bc90cfc81918592ea9489638313`.

## Installation et données

Windows 11, WSL Ubuntu, Node 24, pnpm 11.25 et Python 3.14 réutilisés. Docker Desktop installé pour cet utilisateur, Engine 29.8.2, Compose 5.5.1. Environnement Python isolé avec pypdf et tzdata. Ollama facultatif et Qwen2.5 1.5B installés dans Docker, sans port public.

SQLite WAL + index spatial RTree remplacent le besoin de PostGIS pour deux villes, un seul écrivain et des lectures bornées. Les versions JSON immuables et le pointeur transactionnel évitent les états mixtes. Le conteneur web utilise le runtime Next standalone de production ; le build Vinext existant reste disponible pour Sites.

Version réelle validée : `20261007T083815-9a892566ba03`. Laval : 34 communes, 7 410 mutations ; Tours : 22 communes, 21 088 mutations. Millésimes DVF découverts : 2021–2025. GTFS, ANIL, LOVAC, contexte GASPAR, documents et permis Sitadel importés. Tours dispose des contours OLL ; aucune couverture OLL Laval trouvée. Six mutations de l'ancien snapshot hors périmètre ont été exclues au bootstrap, sans modifier les snapshots d'origine.

Plusieurs synchronisations complètes successives : zéro erreur et aucune nouvelle version pour des résultats identiques. Import complet avec cache mesuré : 46,15 s, pic RSS 1 532,76 Mio, CPU utilisateur 20,43 s et système 21,23 s. Cela ne mesure pas un import à cache froid ni les besoins d'un futur serveur. Les plafonds Compose sont réglables indépendamment de la RAM du PC actuel.

## Vérifications exécutées

- 26 tests Python : collecte existante et service, validation des coordonnées/contours, atomicité, doublons, calendrier GTFS, verrouillage, erreurs réseau, sauvegarde/restauration, API et IA indisponible.
- Tests existants analyse, UI, worker réel en thread Node et assets du build : réussis.
- Build Vinext et build Docker Next production : réussis. TypeScript : réussi après génération des types de routes Next.
- Edge réel, WebGL, desktop 1600×1000 et mobile 390×844 : Laval/Tours, couches visibles et interrupteurs, navigation, clics mailles, lignes, arrêts, campus, ventes individuelles, OLL Tours, favoris, comparaison de quatre secteurs, export CSV, rayon et polygone. Recherche de commune et saisie du prix dans le simulateur contrôlées sur les deux formats. Filtres combinés surface/pièces et résultats géographiques vérifiés en desktop. Console sans erreur ; seules annulations de tuiles attendues lors des déplacements relevées dans les requêtes interrompues.
- Corrections issues du navigateur : priorité de sélection entre couches superposées, onglets mobiles qui se chevauchaient et recherche de commune sans centre officiel dans le GeoJSON (repli sur le centre de son contour, aucune adresse inventée). Captures et rapports sous `outputs/browser/`.
- Fixture isolée sur le port 3001 : promotion génération 1 → 2, API et carte actualisées lors du polling normal, sans rechargement ni rebuild.
- Redémarrage des trois conteneurs principaux : même version et données conservées. Healthchecks API/web/scheduler contrôlés.
- Sauvegarde réelle `/backups/backup-20261007`, restauration isolée avec quatre fichiers vérifiés, hashes et intégrité SQLite contrôlés.

## Limites et transfert

Le scheduler est lancé et son heartbeat vérifié ; son déclenchement à 04:00 Paris est testé par horloge simulée, pas par une attente jusqu'au lendemain. Les données OSM et certains points locaux du snapshot initial restent documentés comme tels. Sitadel est borné aux communes centres ; il ne représente pas tous les projets des EPCI. Les documents ne reconfirment pas automatiquement une date ou un fait ancien.

Import complet réel avec Ollama arrêté : zéro erreur, version inchangée, 35,26 s, pic RSS 1 563,87 Mio. Ollama est laissé arrêté à la livraison ; son profil et son modèle restent installés et activables.

L'IA ne publie aucun résultat. Extraction réelle finale de la page officielle UCO de Laval réussie : adresse, capacité de 600 étudiants et date du 12 septembre 2025, avec citations littérales vérifiées et normalisation déterministe. Qwen2.5 1.5B : 51,50 s dont chargement 15,75 s, 158 tokens générés ; un relevé Docker pendant traitement mesurait 2,528 Gio pour Ollama. Les premiers timeouts et sorties invalides ont été placés en revue. Toute extraction acceptée reste proposée. Le modèle peut fournir des sorties non conformes. Les calculs et la synchronisation structurée fonctionnent sans Ollama.

Les archives brutes sont conservées ; leur nettoyage long terme n'est pas automatique. Les versions publiées ont une rétention configurable. Favoris et critères restent dans localStorage.

Créer le paquet : `python scripts/package-release.py`. Transférer `outputs/atlas-invest-docker.zip`, extraire, puis suivre `OPERATIONS.md` (`docker compose up -d --build`, bootstrap, première collecte et sauvegarde). Le paquet contient le code et les snapshots, pas les secrets ni les volumes du PC. Pour déplacer la version actuelle, transférer également la sauvegarde et utiliser la procédure de restauration isolée.

Le seul accès manquant pour déployer sur le serveur final est son accès d'administration, avec l'adresse et le répertoire de destination. Le branchement Sites exige une API de données joignable en HTTPS et sa configuration côté serveur ; `localhost` sur ce PC ne peut pas alimenter le Site public.
