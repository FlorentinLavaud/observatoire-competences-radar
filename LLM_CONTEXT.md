# PROMPT CONTEXT - COMPÉTENCES RADAR PIPELINE

> [INSTRUCTIONS LLM] : Tu es un ingénieur Data & Analytics expert. Prends connaissance du contexte du projet ci-dessous (Architecture, Stack, Structure de fichiers). Attends mes instructions spécifiques pour générer du code, corriger des bugs, ou optimiser l'architecture. Ne réponds pas par un long résumé, confirme juste que tu as compris le contexte.

---

## 1. Présentation du Projet
* **Nom :** Observatoire Compétences Radar — Pipeline Data
* **Objectif :** Pipeline d'ingestion et transformation des offres d'emploi de la filière **industrie manufacturière** (INSEE Section C, divisions 10-33) afin de (1) identifier les métiers/territoires en tension et (2) détecter les compétences manquantes.
* **Sources de données :** API France Travail v2 (Offres d'emploi + API Statistiques d'accès à l'emploi), INSEE.

## 2. Architecture Technique
```text
[ France Travail / INSEE API ]
              │
              ▼
        [ Dagster ]      (Orchestration)
              │
              ▼
        [ DuckDB ]       (Stockage local / OLAP)
              │
              ▼
          [ dbt ]        (Transformation SQL & Marts)
```

## 3. Structure du projet

src/
├── run_ingestion.py           # Point d'entrée du pipeline
├── models.py                  # Schémas Pydantic de validation
├── ingestion/
│   └── fetchFT.py            # Scraper/Client API France Travail
├── orchestration/
│   └── dagster_pipeline.py   # Jobs et ops Dagster
├── utils/
│   ├── logger.py             # Configuration logging (tqdm + rotation)
│   └── duckdb_handler.py     # Gestion de la connexion DuckDB
│
dbt_project/
├── dbt_project.yml           # Configuration dbt
├── profiles.yml              # Profil DuckDB (pointe vers data/radar.duckdb)
└── models/
    ├── staging/stg_offres.sql     # Nettoyage et typage des données brutes
    └── marts/offres_tension.sql    # Calcul des indices de tension (ROME / Département)

data/
└── radar.duckdb              # Base de données DuckDB locale

## 4. Pipeline de Données (Workflow)
Ingestion : Collecte des offres (Filière Industrie) et des indicateurs d'accès à l'emploi via l'API France Travail.

Validation : Normalisation et validation stricte avec Pydantic (src/models.py).

Persistance : Insertion des données brutes/validées dans DuckDB (data/radar.duckdb).

Transformation (dbt) :

staging : Nettoyage, dédoublonnage, extraction des compétences et départements.

marts : Croisement entre le volume d'offres scrappées et le taux de retour à l'emploi pour générer l'indice de tension par métier/territoire.

Export : Fichiers Parquet prêts pour de la dataviz ou de l'analyse avancée.

[FIN DU CONTEXTE]
