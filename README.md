# Atlas Invest — Laval & Tours

Application React/Vinext + MapLibre, snapshots publics datés. Aucun abonnement de données nécessaire pour les snapshots embarqués. Le projet est conservé dans le dépôt du Site.

## Mise à jour

```sh
python scripts/collect.py --refresh
python scripts/enrich.py --refresh
python scripts/context.py --refresh
```

L’ordre importe : collecte de base, campus/permis, OLL/LOVAC. Les ressources brutes sont conservées dans `data/raw` ; les snapshots distribués sont dans `public/data`. Sans `--refresh`, les téléchargements déjà présents sont réutilisés. Les référentiels upstream peuvent réviser des millésimes anciens. Après collecte, republier le Site pour exposer le nouveau snapshot. Aucun rafraîchissement automatique n’est activé.

`scripts/collect.py` configure les EPCI, centres cartographiques, départements et jeux GTFS. Ajouter une ville implique également de configurer ses points et compléments locaux. Il ne s’agit pas encore d’un connecteur national universel.

## Lancer et vérifier

Installer avec le gestionnaire déclaré dans package.json. `pnpm dev` pour le développement hors environnement supervisé ; `pnpm build` produit le Worker Cloudflare.

```sh
python tests/test_collect.py
node --experimental-strip-types tests/analysis.test.mjs
pnpm exec tsc --noEmit
```

## Méthodes

- DVF 2021–2025 : une mutation, un logement interprétable ; mutations complexes exclues, prix jamais multiplié par le nombre de lignes. Signature des locaux fondée sur parcelle, adresse, type, surface, pièces et lots. Le prix peut inclure des dépendances. Des locaux identiques peuvent rester indiscernables : cette méthode n’est pas une estimation notariale.
- Mailles carrées de 750 m approchés à la latitude de chaque ville. Aucun quartier fictif. Nom du secteur basé sur la rue la plus représentée dans les transactions.
- Prix indicatif d’entrée : médiane €/m² × milieu de la plage de surface demandée. Ce montant n’est pas le prix d’une annonce. Budget total : ajout d’une hypothèse de 8 % de frais, sans travaux ; le simulateur permet les montants exacts.
- Quartiles interpolés. Historique à composition variable, minimum 8 ventes par année. L’année choisie filtre également l’historique. Les extrêmes DVF hors 200–15 000 €/m² sont exclus et comptabilisés.
- ANIL : estimations de loyers d’annonce CC, appartement type T1–T2 non meublé 37 m² au T3 2025. Aucune conversion HC ni extrapolation automatique par surface. `TYPPRED` précise commune ou maille de communes. Attribution : Estimations ANIL, à partir des données du Groupe SeLoger et de leboncoin.
- OLL Tours 2024 : 3 polygones officiels, statistiques HC segmentées ; affectation d’un centre de maille à une zone, sans interpolation dans le quartier. La couche OLL conserve les contours officiels. Laval : aucun OLL trouvé dans les fichiers nationaux 2024/2025 consultés.
- GTFS : arrêts, tracés, lignes, calendriers et exceptions importés ; horaires théoriques actifs à la date de collecte. Intervalles du matin calculés séparément par route et sens ; pas d’itinéraire multimodal ni de temps de marche. Les distances sont à vol d’oiseau.
- Sitadel : tous les permis de logements des communes centres téléchargés ; carte limitée aux programmes ≥20 logements autorisés depuis 2023, états 2/5/6. Codes 2 autorisé, 5 commencé, 6 terminé selon dictionnaire SDES. Nombre de logements = offre potentielle, jamais preuve de demande. Dates de livraison inconnues. Communes périphériques non couvertes par ce connecteur initial de permis.
- Géocodage IGN : contrôler commune/EPCI, conserver type de résultat et précision. Un résultat de type rue ne localise pas précisément un bâtiment.
- LOVAC : vacance du parc privé administrative par commune ; pas vacance locative ni rendement. Secret statistique conservé.
- Géorisques : tentative API v1 échouée (502) lors de cette réalisation ; aucune absence de risque n’est déduite. Consultation officielle proposée. DPE de lot non attribué ; PLU/IRIS et recensement détaillé non intégrés dans cette version.

## Indice de prospection

Disponible uniquement si les campus sont renseignés, les trois dimensions existent, les poids totalisent plus de zéro et le seuil de ventes est atteint. Les poids sont modifiables ; la stratégie étudiante privilégie la proximité. Coût = `clamp(100 × (1 − prix indicatif / (budget × 1.5)), 0, 100)` ; proximité = `max(0, 100 × (1 − distance campus / 5000))` ; profondeur des comparables = `min(100, n/40 × 100)`.

Cet indice ne prétend pas classer intégralement la rentabilité ni le potentiel futur : demande, risques, qualité du bâti et rendement constaté ne sont pas couverts. Les poids affichés expliquent les résultats. Rendement cartographique seulement à partir d’une hypothèse HC explicitement saisie.

## Limites et persistance

Favoris et critères dans localStorage : propres à cet appareil, pas synchronisés. Jusqu’à 4 secteurs comparés ; exports CSV complets. Transactions téléchargées une fois par agglomération (environ quelques Mo compressés), points affichés seulement à zoom élevé ; une API PostGIS paginée sera adaptée à une couverture nationale. GeoJSON maintenu séparé du frontend pour permettre cette migration.

Fournisseur de tuiles configurable au build avec `NEXT_PUBLIC_MAP_TILES` (template `{z}/{x}/{y}`). Par défaut OSM raster, attribution visible, requêtes navigateur avec référent, aucun préchargement massif ni mode hors ligne. À grande échelle, configurer un fournisseur ou une infrastructure dédiée suivant les conditions de service.

WebMCP facultatif : `configure_investment_map`, détecté côté navigateur. Validation navigateur indisponible dans cet environnement ; outil non requis pour l’interface.

Les snapshots DVF ne sont pas exposés sous forme de pages indexables par transaction. Aucun nom de propriétaire n’est récupéré ou affiché. Respecter les conditions de réutilisation et ne pas chercher à réidentifier les personnes.

Les références ANIL 2025 sont sélectionnées selon la typologie : appartement 1–2 pièces (37 m²), 3 pièces et plus (72 m²), ensemble des appartements (52 m²) ou maison (92 m²). Il s’agit de logements de référence, sans extrapolation automatique à la surface du bien.
