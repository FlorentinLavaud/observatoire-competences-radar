# Observatoire Compétences Radar — Documentation du dépôt

## Objectif du projet

Ce dépôt implémente un pipeline de données pour collecter des offres d'emploi France Travail, les transformer et les analyser localement.

L'architecture cible est :

```text
[ France Travail / INSEE ]
           │
           ▼
     [ Dagster ]  (orchestration du pipeline)
           │
           ▼
   [ dbt + DuckDB ] (nettoyage, calcul des indices de tension)
```

## Structure du dépôt

### Racine

- `README.md` : documentation générale et démarrage rapide.
- `REPO_OVERVIEW.md` : documentation détaillée du dépôt (ce fichier).
- `requirements.txt` : dépendances Python du pipeline.
- `docker-compose.yml` : orchestration Docker de Dagster.
- `Dockerfile` : image Python pour l'exécution.
- `dagster/repository.py` : définition du repository Dagster.
- `dbt_project/` : projet dbt DuckDB pour les transformations.
- `src/` : code Python métier.

### `src/`

- `src/run_ingestion.py` : point d'entrée du pipeline.
- `src/ingestion/fetchFT.py` : collecte des offres via l'API France Travail.
- `src/models.py` : schémas Pydantic pour normaliser les données.
- `src/database/backend.sql` : schéma des tables.
- `src/orchestration/dagster_pipeline.py` : jobs et ops Dagster.
- `src/utils/logger.py` : configuration du logger.
- `src/utils/duckdb_handler.py` : gestion DuckDB (stockage).

### `dbt_project/`

- `dbt_project/dbt_project.yml` : configuration dbt.
- `dbt_project/profiles.yml` : profil de connexion DuckDB.
- `dbt_project/models/` : modèles de transformation.
  - `staging/stg_offres.sql` : nettoyage des offres brutes.
  - `marts/offres_tension.sql` : calcul des indices de tension.

## Flux de données

1. **Ingestion** — `src/run_ingestion.py` collecte les offres via France Travail API.
2. **Validation** — Pydantic normalise et valide les données.
3. **Stockage** — DuckDB persiste les offres.
4. **Transformation** — dbt exécute les modèles SQL de nettoyage et d'enrichissement.
5. **Export** — Parquet pour l'analyse.

## Exécution locale

### Backend Python

1. Installer les dépendances :

```bash
pip install -r requirements.txt
```

2. Lancer le pipeline :

```bash
python src/run_ingestion.py
```

3. Lancer Dagster (UI interactive) :

```bash
dagster dev -w dagster/repository.py
```

4. Exécuter dbt :

```bash
dbt run --project-dir dbt_project --profiles-dir dbt_project
```

### Docker

1. Copier les variables d'environnement.
2. Lancer Dagster :

```bash
docker compose up --build
```

## Variables d'environnement requises

- `FRANCE_TRAVAIL_CLIENT_ID`
- `FRANCE_TRAVAIL_SECRET_KEY`

## Points de maintenance

- `src/models.py` — adapter selon l'API France Travail.
- `dbt_project/` — évolver les calculs métiers.
- `src/orchestration/dagster_pipeline.py` — étendre les étapes du pipeline.
