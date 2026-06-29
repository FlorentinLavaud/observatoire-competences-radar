# PROMPT CONTEXT - COMPÉTENCES RADAR PIPELINE

> [INSTRUCTIONS LLM] : Tu es un ingénieur Data & Analytics expert. Prends connaissance du contexte du projet ci-dessous (Architecture, Stack, Structure de fichiers). Attends mes instructions spécifiques pour générer du code, corriger des bugs, ou optimiser l'architecture. Ne réponds pas par un long résumé, confirme juste que tu as compris le contexte.

---

## 1. Présentation du Projet

- **Nom :** Observatoire Compétences Radar — Pipeline Data
- **Objectif :** Pipeline d'ingestion et transformation des offres d'emploi de la filière **industrie manufacturière** (INSEE Section C, divisions 10-33) afin de (1) identifier les métiers/territoires en tension et (2) détecter les compétences manquantes.
- **Sources de données :**
  - API France Travail v2 (Offres d'emploi + Statistiques d'accès à l'emploi)
  - Scraper lindustrie-recrute.fr (portail UIMM, ~118 000 offres)
  - INSEE

---

## 2. Architecture Technique

```text
[ France Travail API ]    [ lindustrie-recrute.fr ]    [ INSEE ]
         │                          │                      │
         └──────────────┬───────────┘                      │
                        ▼                                  │
                  [ Dagster ]      (Orchestration)         │
                        │                                  │
                        ▼                                  │
                  [ DuckDB ]       (Stockage local / OLAP) │
                        │                                  │
                        ▼                                  │
                    [ dbt ]        (Transformation SQL & Marts)
```

---

## 3. Structure du projet

```
src/
├── run_ingestion.py               # Point d'entrée du pipeline
├── models.py                      # Schémas Pydantic de validation
├── ingestion/
│   ├── fetchFT.py                 # Scraper/Client API France Travail
│   ├── fetchEmploiIndustrie.py    # Scraper async lindustrie-recrute.fr
│   └── awswaf/                    # Solver AWS WAF (challenge NetworkBandwidth)
│       ├── aws.py
│       ├── verify.py
│       ├── fingerprint.py
│       ├── crypto.py
│       └── webgl.json
├── orchestration/
│   └── dagster_pipeline.py        # Jobs et ops Dagster
├── utils/
│   ├── logger.py                  # Configuration logging (tqdm + rotation)
│   └── duckdb_handler.py          # Gestion de la connexion DuckDB

dbt_project/
├── dbt_project.yml                # Configuration dbt
├── profiles.yml                   # Profil DuckDB (pointe vers data/radar.duckdb)
└── models/
    ├── staging/stg_offres.sql         # Nettoyage et typage des données brutes
    └── marts/offres_tension.sql        # Calcul des indices de tension (ROME / Département)

data/
└── radar.duckdb                   # Base de données DuckDB locale
```

---

## 4. Sources de données

### France Travail API v2
- Endpoint offres d'emploi, filtré NAF divisions 10–33
- Endpoint `rechercherStatAccesEmploi` pour les indicateurs de retour à l'emploi
- Auth OAuth2 avec refresh automatique
- Ref : https://francetravail.io/produits-partages/catalogue/acces-emploi-demandeurs-emploi/documentation#/api-reference/operations/rechercherStatAccesEmploi

### lindustrie-recrute.fr (UIMM)
- Scraper async (`fetchEmploiIndustrie.py`) sur ~118 000 IDs (700 000 → 818 356)
- Bypass AWS WAF via solver cryptographique (`awswaf/`) — challenge type `NetworkBandwidth`
- Parsing JSON-LD `JobPosting` + sélecteurs CSS spécifiques au template UIMM
- Schéma de sortie normalisé et aligné sur France Travail pour fusion en aval
- Sortie : `lindustrie_offres.jsonl` → `lindustrie_offres.parquet` (zstd)
- Checkpoint résumable via `--resume`

---

## 5. Pipeline de Données (Workflow)

1. **Ingestion** : Collecte des offres (France Travail + UIMM) et des indicateurs d'accès à l'emploi.
2. **Validation** : Normalisation et validation stricte avec Pydantic (`src/models.py`).
3. **Persistance** : Insertion des données brutes/validées dans DuckDB (`data/radar.duckdb`).
4. **Transformation (dbt)** :
   - `staging` : Nettoyage, dédoublonnage, extraction des compétences et départements.
   - `marts` : Croisement entre le volume d'offres scrappées et le taux de retour à l'emploi pour générer l'indice de tension par métier/territoire.
5. **Export** : Fichiers Parquet prêts pour dataviz ou analyse avancée.

---

## 6. Backend & Infra

- DuckDB sur GCP pour le stockage
- Orchestration avec Dagster, déploiement sur OVH Cloud


[FIN DU CONTEXTE]