-- stg_stat_acces_emploi.sql
-- Nettoyage et typage des statistiques d'accès à l'emploi brutes

WITH source AS (
    SELECT * FROM {{ source('radar', 'raw_stat_acces_emploi') }}
),

cleaned AS (
    SELECT
        COALESCE(code_rome, rome_query)                         AS code_rome,
        libelle_rome,
        COALESCE(code_departement, dept_query)                  AS code_departement,
        libelle_departement,
        annee,
        COALESCE(duree_acces_emploi, duree_mois)               AS duree_acces_emploi_mois,
        CAST(taux_acces_emploi AS DOUBLE)                       AS taux_acces_emploi,
        nb_demandeurs,
        type_sortie,
        CURRENT_TIMESTAMP                                        AS _loaded_at
    FROM source
    WHERE taux_acces_emploi IS NOT NULL
      AND code_rome IS NOT NULL
      AND code_departement IS NOT NULL
)

SELECT * FROM cleaned