# Atlas Invest : exploitation locale et Docker

Le frontend React et MapLibre est conservé. Docker utilise le serveur de production Next.js standalone déjà fourni par les dépendances du projet. Vinext et les scripts Sites restent disponibles pour la cible Cloudflare. Le service Python fournit des versions immuables ; le navigateur recharge les données lorsqu’un nouveau manifeste apparaît, sans recompilation du frontend.

SQLite contient les migrations, versions, tâches, verrous, événements et transactions. Son index RTree sert les recherches par emprise. Pour les deux agglomérations actuelles, PostGIS ajouterait un service sans besoin démontré. Une couverture nationale nécessiterait de réévaluer ce choix et la distribution de transactions au navigateur.

## Démarrage

Depuis le dossier du projet, sous Linux :

```sh
docker compose up -d --build
docker compose ps
docker compose exec -T data python -m service.manage bootstrap
docker compose exec -T data python -m service.pipeline
docker compose logs --tail 100 scheduler
```

Sous Windows, `scripts/atlas.ps1` retrouve aussi le Docker Desktop installé pour cet utilisateur :

```powershell
.\scripts\atlas.ps1 up -d --build
.\scripts\atlas.ps1 ps
.\scripts\atlas.ps1 exec -T data python -m service.pipeline
```

Application : http://127.0.0.1:3000. L’API et Ollama ne publient aucun port hôte. Le bind web reste local par défaut. Les limites CPU/RAM dans `.env.example` sont configurables pour le futur PC ; elles ne constituent pas des performances garanties.

Le premier bootstrap conserve le snapshot fourni, avec exclusion documentée des mutations dont le logement retenu sort du périmètre. Il ne constitue pas une nouvelle collecte. Une collecte réelle est une commande distincte et apparaît dans `/api/atlas/status`.

## Synchronisation et rollback

```sh
docker compose exec -T data python -m service.pipeline --source dvf --city laval
docker compose exec -T data python -m service.pipeline --source gtfs --force
docker compose exec -T data python -m service.pipeline --dry-run
docker compose exec -T data python -m service.manage status
docker compose exec -T data python -m service.manage rollback VERSION_ID
```

`--dry-run` autorise découverte, cache et validation, mais ne promeut aucune version. `--force` force les téléchargements de la source choisie. Une collecte quotidienne à 04:00 Europe/Paris se lance dans le conteneur scheduler, avec date locale persistée pour éviter les doublons au changement d’heure. Les calendriers GTFS sont évalués à la date consultée ; le frontend vérifie aussi le changement de jour.

Les ressources GTFS sont vérifiées quotidiennement. DVF, ANIL, OLL, LOVAC, référentiels et documents sont vérifiés au plus une fois par semaine en cache, sauf commande forcée. ETag et Last-Modified servent aux vérifications conditionnelles. Le hash détecte les révisions de ressources inchangées en URL ; les objets bruts sont archivés par hash. Les cinq dernières années présentes dans l’index officiel DVF sont découvertes, sans plage annuelle codée en dur.

Chaque source travaille sur une copie isolée. Un échec conserve la source de la version précédente et marque le run `partial`, avec l’erreur visible dans Sources. Les contrôles globaux rejettent notamment les données essentielles vides, mutations dupliquées, coordonnées invalides et incohérences OLL. Le pointeur de version est commité après fermeture, validation et synchronisation des fichiers. Un verrou global renouvelé empêche deux imports incompatibles ; après crash, son bail expire en trois minutes. Il protège aussi sauvegarde et rollback.

La rétention conserve au moins deux versions, huit par défaut, et la version active. Les fichiers expirés bénéficient de sept jours de grâce avant suppression. Les ressources brutes sont conservées pour audit ; leur purge automatique n’est pas activée. Surveiller leur volume avant un déploiement durable. Les favoris et critères restent dans localStorage, sans migration destructrice ni secret navigateur.

## API

| Route interne | Usage |
|---|---|
| `/health` | état et version active |
| `/api/v1/manifest` | version complète courante |
| `/api/v1/cities` | configuration des villes |
| `/api/v1/status` | dix derniers runs et erreurs |
| `/api/v1/events` | cinquante dernières nouveautés |
| `/api/v1/versions/VERSION/laval.json` | secteurs calculés dans le frontend à partir des transactions, communes, références et contexte de cette version |
| `/api/v1/versions/VERSION/tours.json` | même contrat pour Tours |
| `/api/v1/versions/VERSION/sources.json` | catalogue et provenance |
| `/api/v1/versions/VERSION/points.json` | points, campus et projets |
| `/api/v1/versions/VERSION/laval/transport?date=2026-10-07` | services théoriques à une date ISO |
| `/api/v1/versions/VERSION/laval/transactions?limit=200&offset=0&bbox=-0.9,48,-0.6,48.2` | pagination et index spatial |

La limite est de 1 000 transactions par requête. Les JSON de version sont immuables et cacheables. Le frontend charge la version une fois par ville, puis n’interroge que le manifeste/statut ; les mouvements de carte ne retéléchargent pas la base.

L’application Node passe par `/api/atlas/...` vers `ATLAS_DATA_URL`. Aucune route de synchronisation administrative n’est exposée : les commandes d’administration restent dans le conteneur. `ATLAS_READ_TOKEN`, si défini côté API, impose un bearer de lecture ; le serveur web utilise alors `ATLAS_DATA_READ_TOKEN`. CORS reste fermé sauf origines explicites `ATLAS_CORS_ORIGINS`.

## Sauvegarde et restauration

```sh
docker compose exec -T data python -m service.manage backup /backups/backup-2026-10-07
docker compose cp data:/backups/backup-2026-10-07 ./backup-2026-10-07
```

La sauvegarde associe SQLite, releases, cache brut et revue documentaire sous verrou. Elle retire les baux d’import dans la copie, pour ne pas bloquer une restauration. Pour restaurer, utiliser une nouvelle destination vide et arrêter l’API de cette destination pendant la copie :

```sh
ATLAS_STATE=/chemin/nouvelle-instance python -m service.manage restore /chemin/backup
```

Ne pas copier directement une base SQLite active avec son WAL. Ne pas restaurer par-dessus une instance active. Les tests exercent une restauration dans un répertoire isolé puis la vérification des hashes et un rollback. Les volumes existants ne sont jamais supprimés par les commandes livrées.

## IA facultative

```sh
docker compose --profile ai up -d ollama
docker compose exec -T ollama ollama pull qwen2.5:1.5b
docker compose exec -T -e OLLAMA_MODEL=qwen2.5:1.5b -e OLLAMA_URL=http://ollama:11434 data python -m service.ai_check
```

Qwen 2.5 1,5B fait environ 986 Mo, licence Apache 2.0 selon sa fiche officielle. Il ne remplace pas un extracteur expert. `OLLAMA_MODEL` reste vide par défaut ; pour activer le scheduler documentaire, le renseigner dans `.env`. Un service Ollama existant peut être configuré sans démarrer le profil `ai`. Aucun port Ollama n’est publié ; aucun GPU n’est supposé.

Seuls les documents configurés sont téléchargés. HTML/PDF est parsé par le code ; le modèle reçoit du texte borné et un schéma JSON. Citations absentes, nombres non justifiés, dates non prouvées ou sorties invalides restent en revue. Même une sortie validée est `proposé` et nécessite une revue avant publication de nouveaux faits. Le modèle n’a aucun outil, ne géocode rien et ne calcule aucun score, loyer ou prix.

## Ajouter une ville plus tard

Ajouter une entrée validée dans `config/cities.json`, après vérification officielle de l’INSEE/EPCI et du GTFS. Ajouter les sources locales nécessaires dans `config/local-sources.json`. La même interface et le même pipeline sont réutilisés. Les connecteurs OLL/Sitadel et documents doivent être revus pour chaque territoire ; il n’existe aucune promesse de couverture locale universelle. Ne lancer aucun nouvel import national pour cette configuration.

## Cible Sites et serveur futur

L’identité Sites `appgprj_6ac54bc90cfc81918592ea9489638313` est conservée. Le site publié n’est pas mis à jour par un import local Docker. Pour le brancher, le futur serveur doit fournir un endpoint HTTPS accessible depuis le Worker Sites ; configurer `ATLAS_DATA_URL=https://DOMAINE_DU_SERVICE` et éventuellement `ATLAS_DATA_READ_TOKEN` côté Worker, puis publier les sources vérifiées du même Site. Le proxy serveur évite de placer un token dans le navigateur et évite le besoin de CORS entre navigateur et API. Une adresse localhost ou privée inaccessible au Worker ne peut pas servir de branchement distant.

L’accès au futur serveur et son domaine HTTPS ne sont pas fournis aujourd’hui. Aucun déploiement SSH, changement DNS ou publication du Site distant n’est présumé effectué.

## Vérifications

```sh
python tests/test_collect.py
python -m unittest tests.test_service
node tests/analysis.test.mjs
node tests/ui.test.mjs
node tests/worker.test.mjs
pnpm exec tsc --noEmit
node tests/browser.test.cjs
```

Sous Windows, utiliser `.venv/Scripts/python.exe` pour les tests incluant le fuseau Europe/Paris. `tests/browser.test.cjs` utilise Edge et Playwright installé ; définir `ATLAS_PLAYWRIGHT` pour un autre chemin de package. Il ne remplace pas les tests par un mock MapLibre. Les captures, erreurs réseau et résultats se trouvent dans `outputs/browser`.

La démonstration sans rebuild utilise uniquement une stack et un volume synthétiques :

```sh
docker compose -f compose.demo.yaml up -d
node tests/e2e-version.cjs
docker compose -f compose.demo.yaml stop
```

Le test promeut une génération de fixture et attend le poll normal de la carte, sans reload ni rebuild. La stack de production n’est pas modifiée par cette démonstration.
