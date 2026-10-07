# Atlas Invest

Carte de prospection immobilière pour Laval Agglomération et Tours Métropole. React, TypeScript et MapLibre ; API Python versionnée, SQLite et collecte automatique. Les ventes DVF sont historiques : Atlas ne fournit pas des annonces disponibles.

## Installation rapide avec Docker

Prérequis : Git, Docker Engine avec Compose v2, ou Docker Desktop sous Windows avec WSL 2. Docker doit être démarré. Node et Python sur l’hôte ne sont pas nécessaires pour exécuter les conteneurs.

### Windows — PowerShell

```powershell
git clone https://github.com/Nitraxenius/AtlasInvest.git
cd AtlasInvest
Copy-Item .env.example .env
.\scripts\atlas.ps1 up -d --build
.\scripts\atlas.ps1 exec -T data python -m service.manage bootstrap
.\scripts\atlas.ps1 exec -T data python -m service.pipeline
.\scripts\atlas.ps1 ps
```

### Linux / macOS

```sh
git clone https://github.com/Nitraxenius/AtlasInvest.git
cd AtlasInvest
cp .env.example .env
docker compose up -d --build
docker compose exec -T data python -m service.manage bootstrap
docker compose exec -T data python -m service.pipeline
docker compose ps
```

Ouvrir **http://127.0.0.1:3000**. Le premier build télécharge les dépendances ; la première collecte nécessite Internet. Le bootstrap sert les snapshots inclus ; la collecte suivante récupère et valide les sources réelles. Un connecteur indisponible conserve ses dernières données valides et signale l’erreur dans Sources.

La collecte quotidienne démarre à **04:00 Europe/Paris**, tant que le PC et Docker fonctionnent. Une promotion validée apparaît sur la carte au prochain polling, sans rebuild. Les favoris et critères restent dans le navigateur.

## Configurer le futur PC

Modifier `.env` pour le port, les limites CPU/RAM et le modèle facultatif. Les plafonds mémoire restent réglables ; ils ne dépendent pas de la RAM du PC de développement. Le port web est limité à localhost par défaut. API et Ollama n’exposent aucun port hôte.

Configurer les villes dans `config/cities.json` et les sources locales dans `config/local-sources.json`. Ajouter un territoire peut nécessiter un connecteur local : la couverture n’est pas universelle.

## Mise à jour du logiciel

Sauvegarder avant une mise à jour. Sous Windows, remplacer `docker compose` par `.\scripts\atlas.ps1` si Docker n’est pas dans le PATH.

```sh
docker compose exec -T data python -m service.manage backup /backups/avant-mise-a-jour
git pull --ff-only
docker compose up -d --build
docker compose ps
```

Les volumes conservent données et versions lors du remplacement des images. Ne pas utiliser `docker compose down -v` pour une mise à jour.

```sh
docker compose logs --tail 100 scheduler
docker compose exec -T data python -m service.pipeline
docker compose exec -T data python -m service.manage status
docker compose stop
docker compose up -d
```

## IA locale facultative

Les imports structurés et calculs fonctionnent sans IA. Pour démarrer Ollama et installer le petit modèle testé :

```sh
docker compose --profile ai up -d ollama
docker compose exec -T ollama ollama pull qwen2.5:1.5b
docker compose exec -T -e OLLAMA_MODEL=qwen2.5:1.5b data python -m service.ai_check
```

Renseigner `OLLAMA_MODEL` dans `.env`, puis recréer le scheduler pour activer l’extraction documentaire automatique. Les sorties restent proposées en file de revue ; elles ne modifient pas automatiquement prix, loyers, scores ou carte.

## Documentation

- [Exploitation, synchronisation, sauvegarde, restauration et rollback](docs/OPERATIONS.md)
- [Catalogue des sources et limites](docs/SOURCES.md)
- [Tests exécutés, mesures et limites restantes](docs/VALIDATION.md)
- [Méthodologie du snapshot initial](docs/METHODOLOGY.md)
- [Historique des versions](CHANGELOG.md)

## Développement et tests

Node 22.13 ou supérieur, pnpm 11.25 et Python 3.14. Respecter le lockfile :

```sh
pnpm install --frozen-lockfile
python -m venv .venv
# Activer .venv selon le système, puis :
python -m pip install -r requirements.txt
pnpm dev
python -m unittest tests.test_collect tests.test_service
node tests/analysis.test.mjs
node tests/ui.test.mjs
node tests/worker.test.mjs
```

Les tests navigateur nécessitent Playwright et un navigateur Edge installé ; configurer `ATLAS_PLAYWRIGHT` si son package n’est pas dans le chemin de la machine initiale. Voir le guide d’exploitation. Le build Docker utilise Next standalone en production ; le build Vinext/Sites existant est conservé.

## Données et publication

Les snapshots embarqués et le cache initial sont des données publiques datées, avec attribution dans le catalogue. Les nouveaux caches, volumes, modèles, sauvegardes et secrets ne sont pas versionnés. Les licences des sources restent distinctes de celles des dépendances.

Le déploiement Docker et le Site public sont deux cibles séparées. Une collecte locale ne republie pas le Site. Le branchement Sites exige une API HTTPS accessible depuis son serveur ; voir le guide d’exploitation.
