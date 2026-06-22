# Observatoire Compétences Radar — Pipeline Data

Pipeline d'ingestion et transformation des offres d'emploi de la filière **industrie manufacturière** (INSEE Section C, divisions 10-33) via l'API **France Travail v2**.

**Architecture simplifiée:**

```text
[ France Travail API ]
         │
         ▼
   [ Dagster ]  (orchestration)
         │
         ▼
   [ DuckDB ]  (stockage)
         │
         ▼
   [ dbt ]  (transformation)
```

---

## Démarrage rapide

### Installation

1. **Créer un environnement virtuel:**

```bash
python -m venv venv
```

2. **Activer l'environnement virtuel:**

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

3. **Installer les dépendances:**

```bash
pip install -r requirements.txt
```

### Variables d'environnement

Créer un fichier `.env` à la racine:

```bash
cp .env.example .env
```

Puis éditer avec vos identifiants:

```
FRANCE_TRAVAIL_CLIENT_ID=votre_client_id
FRANCE_TRAVAIL_SECRET_KEY=votre_secret_key
```

### Exécution

**Lancer le pipeline directement:**

```bash
python src/run_ingestion.py
```

**Lancer avec Dagster (UI interactive):**

```bash
dagster dev -w dagster/repository.py
```

Puis ouvrir http://localhost:3000

**Exécuter les transformations dbt:**

```bash
dbt run --project-dir dbt_project --profiles-dir dbt_project
```

---

## Structure du projet

```
src/
├── run_ingestion.py           # Point d'entrée du pipeline
├── models.py                  # Schémas Pydantic de validation
├── ingestion/
│   └── fetchFT.py            # Scraper France Travail API
├── orchestration/
│   └── dagster_pipeline.py   # Jobs et ops Dagster
├── utils/
│   ├── logger.py             # Configuration logging
│   └── duckdb_handler.py     # Gestion DuckDB
│
dbt_project/
├── dbt_project.yml           # Configuration dbt
├── profiles.yml              # Profil DuckDB
└── models/
    ├── staging/stg_offres.sql      # Nettoyage des données brutes
    └── marts/offres_tension.sql    # Calcul des indices de tension

data/
└── radar.duckdb              # Base de données DuckDB locale
```

---

## Pipeline de données

1. **Ingestion** — Collecte les offres via France Travail API
2. **Validation** — Normalise les données avec Pydantic
3. **Persistance** — Stocke dans DuckDB
4. **Transformation** — dbt nettoie et enrichit les données
5. **Export** — Parquet pour analyse

---

## Architecture cible

```text
[ France Travail / INSEE ]
           │
           ▼
     [ Dagster ]  (orchestration du pipeline)
           │
           ▼
   [ dbt + DuckDB ] (nettoyage, calcul des indices de tension)
```

### Composants

- `dagster/` : jobs et repository pour orchestrer l'ingestion
- `dbt_project/` : modèles dbt pour transformation analytique
- `src/` : code Python métier

---

## Sorties, monitoring & logs

### Console

- Progression en temps réel via des barres **tqdm**
- Flux de logs isolé de l'affichage de progression

### Système de fichiers

- Logs générés dans `logs/scraper.log` avec rotation journalière


https://francetravail.io/produits-partages/catalogue/acces-emploi-demandeurs-emploi/documentation#/api-reference/operations/rechercherStatAccesEmploi