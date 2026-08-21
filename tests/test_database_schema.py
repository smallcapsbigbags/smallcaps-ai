from database.models import AnalystRunRow


def test_orm_declares_one_current_run_unique_index():
    indexes = {index.name: index for index in AnalystRunRow.__table__.indexes}
    index = indexes["uq_analyst_runs_one_current"]
    assert index.unique is True
