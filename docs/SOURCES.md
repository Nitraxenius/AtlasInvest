# Catalogue des connecteurs

Les métadonnées précises du dernier import sont dans `sources.json` de sa version API. Elles conservent producteur, page, fichier, ID de ressource, licence, période, publication connue, collecte, hash, méthode, échelle et limites. Les dates de collecte ne deviennent jamais un millésime statistique.

| Source | Découverte et périmètre | Limites conservées |
|---|---|---|
| [Découpage administratif](https://geo.api.gouv.fr/) | EPCI Laval 200083392 et Tours 243700754 ; centres 53130 et 37261 confirmés le 7 octobre 2026 | contours communaux, pas quartiers |
| [DVF géolocalisées](https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees) | index officiel, cinq dernières années, départements 53/37 puis filtrage EPCI | prix de mutation unique, dépendances possibles, exclusions multi-biens ; année partielle exclue des tendances |
| [Transport Laval](https://transport.data.gouv.fr/datasets/offre-de-transport-du-reseau-de-laval-agglomeration-gtfs) | ressource statique officielle, délégation RATP Dev autorisée seulement au chemin Laval | GTFS théorique, sens et calendriers, aucun tracé inventé |
| [Transport Tours](https://transport.data.gouv.fr/datasets/fil-bleu-syndicat-des-mobilites-gtfs-gtfs-rt) | ressource GTFS statique, indépendante du GTFS-RT | aucun temps réel annoncé |
| [ANIL](https://www.data.gouv.fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025) | recherche de la nouvelle édition et quatre typologies | loyers CC pour logements de référence 37/52/72/92 m², pas conversion HC ni extrapolation |
| [OLL](https://www.data.gouv.fr/datasets/resultats-des-observatoires-locaux-des-loyers-par-agglomeration) | archive Tours L3700 contenant statistiques et contours du même millésime | HC observé, secret statistique ; aucune couverture Laval déduite ou inventée |
| [LOVAC](https://www.data.gouv.fr/datasets/logements-vacants-du-parc-prive-par-commune-departement-region-france-de-2020-a-2026) | catalogue puis fichier Communes, colonne INSEE découverte | valeurs secrétisées conservées, pas vacance locative investisseur |
| [Sitadel](https://www.data.gouv.fr/datasets/liste-des-permis-de-construire-et-autres-autorisations-durbanisme) | ressource logements courante via API tabulaire, communes centres seulement | statuts 2/5/6, géocodage limité/cache ; autorisation différente de livraison |
| [Géorisques](https://www.georisques.gouv.fr/) | GASPAR commune centre | contexte communal, pas rapport du bien ni preuve d’absence de risque |
| [IGN](https://data.geopf.fr/geocodage/search) | adresses des permis, cache et appartenance EPCI | précision conservée ; rue différente d’un bâtiment |
| [OpenStreetMap](https://www.openstreetmap.org/copyright) | fond raster actuel et points du snapshot initial | attribution ODbL ; points OSM non rafraîchis automatiquement par le nouveau pipeline |

Les sources locales du fichier `config/local-sources.json` sont récupérées chaque semaine. Leurs faits initiaux restent accompagnés des sources et dates du snapshot ; récupérer un document ne reconfirme pas automatiquement son contenu. Les nouvelles extractions restent dans la file de revue. Les domaines autorisés sont bornés aux producteurs et aux documents explicitement configurés. Les échecs de téléchargement ne sont pas traités comme des sources vides.
