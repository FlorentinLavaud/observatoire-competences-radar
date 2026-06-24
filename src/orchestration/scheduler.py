from dagster import schedule

from src.orchestration.dagster_pipeline import france_travail_pipeline, job_stat_acces_emploi


@schedule(
    job=france_travail_pipeline,
    cron_schedule="0 6 * * *",
    execution_timezone="Europe/Paris",
)
def daily_france_travail_schedule(_context):
    return {}


@schedule(
    job=job_stat_acces_emploi,
    cron_schedule="0 7 * * 1",  # lundi matin — données hebdo suffisantes
    execution_timezone="Europe/Paris",
)
def weekly_stat_acces_emploi_schedule(_context):
    return {}