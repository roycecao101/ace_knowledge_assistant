"""Add only ingestion tables to an existing deployment; never alters auth records."""
from .database import database
from .knowledge_models import KnowledgeState, Document, Passage, PassageTerm, DiscrepancyScan, Discrepancy
from sqlalchemy import inspect, text

def initialize(engine):
    for model in (KnowledgeState, Document, Passage, PassageTerm, DiscrepancyScan, Discrepancy):
        model.__table__.create(engine, checkfirst=True)
    # Only nullable metadata columns are added; no existing rows are rewritten.
    with engine.begin() as connection:
        scan_columns = {c['name'] for c in inspect(connection).get_columns('discrepancy_scan')}
        if 'revision' not in scan_columns:
            connection.execute(text('ALTER TABLE discrepancy_scan ADD COLUMN revision VARCHAR(64)'))
        columns = {c['name'] for c in inspect(connection).get_columns('discrepancies')}
        for name, kind in (('issue_id', 'VARCHAR(64)'), ('evidence_pairs', 'JSON')):
            if name not in columns:
                connection.execute(text(f'ALTER TABLE discrepancies ADD COLUMN {name} {kind}'))

if __name__ == '__main__':
    engine, _ = database()
    initialize(engine)
    engine.dispose()
    print('Knowledge tables initialized; existing accounts preserved.')
