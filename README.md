# Radar Ingestion Pipeline

Pipeline de collecte, validation et synchronisation des offres d'emploi de la filière **industrie manufacturière** (Section C de la nomenclature INSEE, divisions 10 à 33) via l'API **France Travail v2** vers **Supabase**.

---

## Architecture des composants

```text
src/
├── database.py
│   └── Gestion de l'instance client Supabase & upsert par batchs
│
├── models.py
│   └── Schéma de validation et nettoyage sémantique (Pydantic v2)
│
├── run_ingestion.py
│   └── Orchestrateur et point d'entrée du pipeline
│
├── ingestion/
│   └── france_travail_scrapper.py
│       └── Scraper orienté POO
│           (Gestion OAuth2, Range HTTP 206/204)
│
└── utils/
    └── logger.py
        └── Configuration de logging asynchrone
            compatible TQDM & File Rotation
```

---

## Spécifications techniques

### Pagination API

Implémentation du système de plages (`range: 0-149`) via analyse récursive des codes réponses :

- **206** — Partial Content
- **204** — No Content

### Débit & résilience

- Temporisation de **150 ms** entre les requêtes
- Respect de la contrainte de quota : **10 requêtes/seconde**

### Validation sémantique

- Typage fort avec **Pydantic v2**
- Transformation des structures JSON imbriquées
- Aplatissement des payloads avant insertion en base

### Persistance

Écriture optimisée dans PostgreSQL via l'interface **`.upsert()`** de Supabase :

- Insertion par lots configurables de **200 enregistrements**
- Résolution native des collisions sur clé primaire

---

## Configuration de l'environnement

Le pipeline requiert les variables d'environnement suivantes :

### France Travail API

```bash
export FRANCE_TRAVAIL_CLIENT_ID="votre_client_id"
export FRANCE_TRAVAIL_SECRET_KEY="votre_secret_key"
```

### Instance Supabase

```bash
export SUPABASE_URL="https://votre-projet.supabase.co"
export SUPABASE_KEY="votre-anon-ou-service-role-key"
```

---

## Déploiement & exécution

### Installation des dépendances

```bash
pip install requests pydantic supabase tqdm
```

### Exécution du pipeline

```bash
python src/run_ingestion.py
```

---

## Sorties, monitoring & logs

### Console

- Progression en temps réel via des barres **tqdm**
- Flux de logs isolé de l'affichage de progression

### Système de fichiers

- Rotation journalière des logs
- Fichier principal :

```text
logs/scraper.log
```
