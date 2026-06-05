-- Table principale des offres d'emploi
CREATE TABLE offres (
    id VARCHAR PRIMARY KEY,
    source VARCHAR NOT NULL DEFAULT 'france_travail',
    titre VARCHAR NOT NULL,
    description TEXT,
    code_rome VARCHAR,
    rome_libelle VARCHAR,
    code_naf VARCHAR,
    secteur_activite VARCHAR, -- Division à 2 chiffres
    secteur_libelle VARCHAR,
    nom_acheteur VARCHAR, -- Nom de l'entreprise
    type_contract VARCHAR,
    type_contrat_libelle VARCHAR,
    experience_exige VARCHAR,
    code_departement VARCHAR,
    offres_manque_candidats BOOLEAN DEFAULT FALSE, -- Indicateur de tension du marché
    date_parution TIMESTAMP WITH TIME ZONE,
    date_extraction TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Table du référentiel des compétences (inchangée, utile pour tes jointures)
CREATE TABLE competences_referentiel (
    code_competence VARCHAR PRIMARY KEY,
    libelle VARCHAR NOT NULL,
    categorie VARCHAR
);

-- Table de liaison pour les compétences détectées
CREATE TABLE competences_extraites (
    offre_id VARCHAR REFERENCES offres(id) ON DELETE CASCADE,
    code_competence VARCHAR, -- Code ou libellé selon ta stratégie NLP de mapping
    score_confiance FLOAT DEFAULT 1.0,
    methode_extraction VARCHAR NOT NULL, -- 'regex', 'ner_camembert', 'llm'
    date_extraction TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (offre_id, code_competence)
);

CREATE INDEX idx_offres_rome ON offres(code_rome);
CREATE INDEX idx_offres_secteur ON offres(secteur_activite);