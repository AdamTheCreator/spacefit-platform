"""
One-time data migration: group existing documents into Projects.

Logic:
1. Group ParsedDocuments by (user_id, property_id) → create a Project per group.
2. Orphan documents (no property_id) → create an "Uncategorized" project per user.
3. Link existing ChatSessions (via source_document_id) to the same project.

Usage:
    cd backend && python -m scripts.migrate_documents_to_projects
"""
import asyncio
import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.db.models.document import ParsedDocument
from app.db.models.chat import ChatSession
from app.db.models.deal import Property
from app.db.models.project import Project

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Fetch all documents not yet in a project
        result = await db.execute(
            select(ParsedDocument).where(ParsedDocument.project_id.is_(None))
        )
        docs = result.scalars().all()
        logger.info("Found %d unlinked documents", len(docs))

        if not docs:
            logger.info("Nothing to migrate.")
            return

        # Group by (user_id, property_id)
        groups: dict[tuple[str, str | None], list[ParsedDocument]] = defaultdict(list)
        for doc in docs:
            groups[(doc.user_id, doc.property_id)].append(doc)

        created = 0
        for (user_id, property_id), group_docs in groups.items():
            # Determine project name
            if property_id:
                prop_result = await db.execute(
                    select(Property).where(Property.id == property_id)
                )
                prop = prop_result.scalar_one_or_none()
                project_name = prop.name if prop else "Imported Property"
            else:
                project_name = "Uncategorized"

            # Check if a project already exists for this combo
            existing = await db.execute(
                select(Project).where(
                    Project.user_id == user_id,
                    Project.property_id == property_id if property_id else Project.property_id.is_(None),
                    Project.name == project_name,
                )
            )
            project = existing.scalar_one_or_none()

            if not project:
                project = Project(
                    user_id=user_id,
                    property_id=property_id,
                    name=project_name,
                )
                db.add(project)
                await db.flush()
                created += 1
                logger.info(
                    "Created project '%s' for user=%s property=%s (%d docs)",
                    project_name, user_id, property_id, len(group_docs),
                )

            # Link documents
            for doc in group_docs:
                doc.project_id = project.id

            # Link chat sessions that reference these documents
            doc_ids = [d.id for d in group_docs]
            sessions_result = await db.execute(
                select(ChatSession).where(
                    ChatSession.source_document_id.in_(doc_ids),
                    ChatSession.project_id.is_(None),
                )
            )
            for session in sessions_result.scalars().all():
                session.project_id = project.id

        await db.commit()
        logger.info(
            "Migration complete: %d projects created, %d documents linked",
            created, len(docs),
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
