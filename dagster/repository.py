from dagster import repository

from src.orchestration.dagster_pipeline import france_travail_pipeline


@repository
def radar_repository():
    return [france_travail_pipeline]
