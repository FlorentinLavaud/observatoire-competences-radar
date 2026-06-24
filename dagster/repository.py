from dagster import Definitions

from src.orchestration.dagster_pipeline import france_travail_pipeline, job_stat_acces_emploi
from src.orchestration.scheduler import (
    daily_france_travail_schedule,
    weekly_stat_acces_emploi_schedule,
)

defs = Definitions(
    jobs=[france_travail_pipeline, job_stat_acces_emploi],
    schedules=[daily_france_travail_schedule, weekly_stat_acces_emploi_schedule],
)