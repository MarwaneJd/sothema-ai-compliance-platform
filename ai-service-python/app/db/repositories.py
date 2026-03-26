import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    AiRequest,
    AiRequestSegment,
    AuditLog,
    ComplianceAnalysis,
    Document,
    TextSegment,
)


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, doc_id: uuid.UUID) -> Document | None:
        result = await self.session.execute(
            select(Document).where(Document.Id == doc_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_segments(self, doc_id: uuid.UUID) -> Document | None:
        result = await self.session.execute(
            select(Document)
            .options(selectinload(Document.text_segments))
            .where(Document.Id == doc_id)
        )
        return result.scalar_one_or_none()

    async def get_by_sharepoint_item_id(self, sp_id: str) -> Document | None:
        result = await self.session.execute(
            select(Document).where(Document.SharePointItemId == sp_id)
        )
        return result.scalar_one_or_none()


class TextSegmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_document_id(self, doc_id: uuid.UUID) -> list[TextSegment]:
        result = await self.session.execute(
            select(TextSegment)
            .where(TextSegment.DocumentId == doc_id)
            .order_by(TextSegment.ChunkIndex)
        )
        return list(result.scalars().all())

    async def bulk_create(self, segments: list[TextSegment]) -> list[TextSegment]:
        self.session.add_all(segments)
        await self.session.flush()
        return segments

    async def get_by_vector_store_ids(
        self, vector_store_ids: list[str]
    ) -> list[TextSegment]:
        result = await self.session.execute(
            select(TextSegment)
            .options(selectinload(TextSegment.document))
            .where(TextSegment.VectorStoreId.in_(vector_store_ids))
        )
        return list(result.scalars().all())

    async def delete_by_document_id(self, doc_id: uuid.UUID) -> list[str]:
        """Delete all segments for a document. Returns list of VectorStoreIds for index cleanup."""
        segments = await self.get_by_document_id(doc_id)
        vector_store_ids = [
            s.VectorStoreId for s in segments if s.VectorStoreId is not None
        ]
        for segment in segments:
            await self.session.delete(segment)
        await self.session.flush()
        return vector_store_ids


class ComplianceAnalysisRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, analysis: ComplianceAnalysis) -> ComplianceAnalysis:
        self.session.add(analysis)
        await self.session.flush()
        return analysis

    async def get_by_id(self, analysis_id: uuid.UUID) -> ComplianceAnalysis | None:
        result = await self.session.execute(
            select(ComplianceAnalysis).where(ComplianceAnalysis.Id == analysis_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        analysis_id: uuid.UUID,
        status: int,
        score: float | None = None,
        summary: str | None = None,
        details: str | None = None,
    ) -> None:
        from sqlalchemy import text as sa_text

        # Use raw SQL to avoid FreeTDS parameterized query size limits
        # on large NVARCHAR(MAX) columns
        analyzed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        set_parts = [f"[Status] = {status}", f"[AnalyzedAt] = '{analyzed_at}'"]

        if score is not None:
            set_parts.append(f"[Score] = {score}")
        if summary is not None:
            escaped = summary.replace("'", "''")
            set_parts.append(f"[Summary] = N'{escaped}'")
        if details is not None:
            escaped = details.replace("'", "''")
            set_parts.append(f"[Details] = N'{escaped}'")

        sql = f"UPDATE [ComplianceAnalyses] SET {', '.join(set_parts)} WHERE [Id] = '{analysis_id}'"
        await self.session.execute(sa_text(sql))
        await self.session.flush()


class AuditLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, log: AuditLog) -> AuditLog:
        self.session.add(log)
        await self.session.flush()
        return log


class AiRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, request: AiRequest) -> AiRequest:
        self.session.add(request)
        await self.session.flush()
        return request


class AiRequestSegmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_create(self, segments: list[AiRequestSegment]) -> None:
        self.session.add_all(segments)
        await self.session.flush()
