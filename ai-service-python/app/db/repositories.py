import uuid
from datetime import datetime

from sqlalchemy import select, text as sa_text, update
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
        # Use raw SQL with CAST to bypass FreeTDS parameter binding truncation
        # on NVARCHAR(MAX) columns (FreeTDS sends strings as bounded VARCHAR)
        for seg in segments:
            await self.session.execute(
                sa_text(
                    "INSERT INTO [TextSegments] "
                    "([Id], [DocumentId], [Content], [ChunkIndex], [VectorStoreId], [CreatedAt]) "
                    "VALUES (:id, :doc_id, CAST(:content AS NVARCHAR(MAX)), :chunk_idx, :vs_id, :created)"
                ),
                {
                    "id": str(seg.Id),
                    "doc_id": str(seg.DocumentId),
                    "content": seg.Content,
                    "chunk_idx": seg.ChunkIndex,
                    "vs_id": seg.VectorStoreId,
                    "created": seg.CreatedAt,
                },
            )
        # Expunge ORM objects so SQLAlchemy doesn't try to flush them again
        for seg in segments:
            if seg in self.session.new:
                self.session.expunge(seg)
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
        # Use raw SQL with CAST to bypass FreeTDS truncation on Details column
        await self.session.execute(
            sa_text(
                "INSERT INTO [AuditLogs] "
                "([Id], [UserId], [Action], [EntityType], [EntityId], [Timestamp], [Details]) "
                "VALUES (:id, :user_id, :action, :entity_type, :entity_id, :ts, CAST(:details AS NVARCHAR(MAX)))"
            ),
            {
                "id": str(log.Id),
                "user_id": log.UserId,
                "action": log.Action,
                "entity_type": log.EntityType,
                "entity_id": log.EntityId,
                "ts": log.Timestamp,
                "details": log.Details,
            },
        )
        return log


class AiRequestRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, request: AiRequest) -> AiRequest:
        # Use raw SQL with CAST to bypass FreeTDS truncation on large text columns
        await self.session.execute(
            sa_text(
                "INSERT INTO [AiRequests] "
                "([Id], [Question], [Response], [CreatedAt]) "
                "VALUES (:id, CAST(:question AS NVARCHAR(MAX)), CAST(:response AS NVARCHAR(MAX)), :created)"
            ),
            {
                "id": str(request.Id),
                "question": request.Question,
                "response": request.Response,
                "created": request.CreatedAt,
            },
        )
        return request


class AiRequestSegmentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_create(self, segments: list[AiRequestSegment]) -> None:
        self.session.add_all(segments)
        await self.session.flush()
