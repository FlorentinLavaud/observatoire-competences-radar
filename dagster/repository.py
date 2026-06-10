from dagster import Definitions
from src.orchestration.dagster_pipeline import france_travail_pipeline
from src.orchestration.scheduler import daily_france_travail_schedule

defs = Definitions(
    jobs=[france_travail_pipeline],
    schedules=[daily_france_travail_schedule],
)