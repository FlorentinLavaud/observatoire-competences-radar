with base as (
    select
        id,
        titre,
        code_rome,
        code_naf,
        secteur_activite,
        secteur_libelle,
        offres_manque_candidats,
        date_parution
    from {{ ref('stg_offres') }}
)

select
    id,
    titre,
    code_rome,
    code_naf,
    secteur_activite,
    secteur_libelle,
    offres_manque_candidats,
    date_parution,
    case
        when offres_manque_candidats then 100
        else 30
    end as tension_index,
    case
        when offres_manque_candidats then 'forte'
        else 'moderee'
    end as tension_segment
from base
