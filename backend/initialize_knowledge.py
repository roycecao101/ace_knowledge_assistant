"""Add only ingestion tables to an existing deployment; never alters auth records."""
from .database import database
from .knowledge_models import KnowledgeState, Document, Passage, PassageTerm

def initialize(engine):
    for model in (KnowledgeState, Document, Passage, PassageTerm):
        model.__table__.create(engine, checkfirst=True)

if __name__ == '__main__':
    engine, _ = database()
    initialize(engine)
    engine.dispose()
    print('Knowledge tables initialized; existing accounts preserved.')
