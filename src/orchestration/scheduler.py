from dagster import schedule

from src.orchestration.dagster_pipeline import france_travail_pipeline

@schedule(
    job=france_travail_pipeline,
    cron_schedule="0 6 * * *",  # tous les jours à 6h
    execution_timezone="Europe/Paris",
)
def daily_france_travail_schedule(_context):
    return {}