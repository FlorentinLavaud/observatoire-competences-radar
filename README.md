# Observatoire Compétences Radar — Pipeline Data

Pipeline d'ingestion et transformation des offres d'emploi de la filière **industrie manufacturière** (INSEE Section C, divisions 10-33) via l'API **France Travail v2** et le scraper **lindustrie-recrute.fr**.

**Architecture simplifiée:**

```text
[ France Travail API ]    [ lindustrie-recrute.fr ]
         │                          │
         └──────────┬───────────────┘
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

**Scraper lindustrie-recrute.fr:**

```bash
# Scraping initial (plage d'IDs complète)
python src/ingestion/fetchEmploiIndustrie.py --start 700000 --end 818356

# Reprise après interruption
python src/ingestion/fetchEmploiIndustrie.py --resume

# Conversion JSONL → Parquet
python src/ingestion/fetchEmploiIndustrie.py --to-parquet
```

**Exécuter les transformations dbt:**

```bash
dbt run --project-dir dbt_project --profiles-dir dbt_project
```

### Déploiement Docker

**Linux/macOS**

```bash
bash deploy.sh
```

**Windows PowerShell**

```powershell
./deploy.ps1
```

---

## Structure du projet

```
src/
├── run_ingestion.py           # Point d'entrée du pipeline
├── models.py                  # Schémas Pydantic de validation
├── ingestion/
│   ├── fetchFT.py             # Client API France Travail
│   ├── fetchEmploiIndustrie.py  # Scraper lindustrie-recrute.fr
│   └── awswaf/                # Solver AWS WAF (bypass challenge JS)
│       ├── aws.py
│       ├── verify.py
│       ├── fingerprint.py
│       ├── crypto.py
│       └── webgl.json
├── orchestration/
│   └── dagster_pipeline.py    # Jobs et ops Dagster
├── utils/
│   ├── logger.py              # Configuration logging
│   └── duckdb_handler.py      # Gestion DuckDB
│
dbt_project/
├── dbt_project.yml            # Configuration dbt
├── profiles.yml               # Profil DuckDB
└── models/
    ├── staging/stg_offres.sql       # Nettoyage des données brutes
    └── marts/offres_tension.sql     # Calcul des indices de tension

data/
└── radar.duckdb               # Base de données DuckDB locale
```

---

## Sources de données

### France Travail API v2
- **Offres d'emploi** : endpoint recherche, filtré sur les divisions NAF 10–33
- **Statistiques d'accès à l'emploi** : endpoint `rechercherStatAccesEmploi`
- Authentification OAuth2, refresh automatique du token
- Référence : https://francetravail.io/produits-partages/catalogue/acces-emploi-demandeurs-emploi/documentation#/api-reference/operations/rechercherStatAccesEmploi

### lindustrie-recrute.fr (UIMM)
- Scraper async sur ~118 000 IDs (700 000 → 818 356)
- Bypass AWS WAF via solver cryptographique (challenge `NetworkBandwidth`)
- Parsing JSON-LD `JobPosting` + sélecteurs CSS UIMM
- Sortie : JSONL + Parquet (compression zstd)
- Schéma normalisé aligné sur France Travail pour fusion en aval

---

## Pipeline de données

1. **Ingestion** — Collecte les offres via France Travail API et scraper UIMM
2. **Validation** — Normalise les données avec Pydantic
3. **Persistance** — Stocke dans DuckDB
4. **Transformation** — dbt nettoie et enrichit les données
5. **Export** — Parquet pour analyse

---

## Architecture cible

```text
[ France Travail API ]    [ lindustrie-recrute.fr ]    [ INSEE ]
         │                          │                      │
         └──────────────┬───────────┘                      │
                        ▼                                  │
                  [ Dagster ]  (orchestration du pipeline) │
                        │                                  │
                        ▼                                  │
            [ dbt + DuckDB ] (nettoyage, calcul indices de tension)
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
- Checkpoint scraper : `lindustrie_checkpoint.txt` (reprise `--resume`)
- Sortie scraper : `lindustrie_offres.jsonl` / `lindustrie_offres.parquet`

---

## Backend & Infra

- DuckDB sur GCP pour le stockage
- Orchestration avec Dagster
- Déploiement sur OVH Cloud

---

## TODO
- [-] Doc méthodo (DARES) sur Notion
- [-] Fix intégration `rechercherStatAccesEmploi` dans Dagster
- [-] Run fetching de Emploi Industrie (Changer l'id de départ + Rate limiter)
- [-] Vérifier le déploiement du fetching de Emploi Industrie 
- [ ] Déployer la pipeline avec serveur GCP
- [ ] Fusion des DB France Travail + Emploi Industrie (déduplication, détection code ROME, Ajout SIREN, Ajout NAF)