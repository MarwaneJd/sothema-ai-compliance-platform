"""SQLAlchemy ORM models matching the .NET EF Core domain entities.

CRITICAL: Column names use PascalCase to match EF Core defaults.
Both services share the same SQL Server database.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "Documents"

    Id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    SharePointItemId = Column(String(500), nullable=False, index=True)
    Title = Column(String(500), nullable=False)
    SiteId = Column(String(500), nullable=False)
    DriveId = Column(String(500), nullable=False)
    ContentType = Column(String(200), nullable=False)
    FileType = Column(String(50), nullable=False)
    SharePointUrl = Column(String(2000), nullable=False)
    UploadedAt = Column(DateTime, nullable=False, default=datetime.utcnow)

    text_segments = relationship("TextSegment", back_populates="document")
    compliance_analyses = relationship("ComplianceAnalysis", back_populates="document")


class TextSegment(Base):
    __tablename__ = "TextSegments"

    Id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    DocumentId = Column(
        UNIQUEIDENTIFIER, ForeignKey("Documents.Id"), nullable=False, index=True
    )
    Content = Column(String, nullable=False)
    ChunkIndex = Column(Integer, nullable=False)
    VectorStoreId = Column(String(100), nullable=True)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)

    document = relationship("Document", back_populates="text_segments")
    ai_request_segments = relationship("AiRequestSegment", back_populates="text_segment")


class ComplianceAnalysis(Base):
    """Status values: Pending=0, Processing=1, Completed=2, Failed=3."""

    __tablename__ = "ComplianceAnalyses"

    Id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    DocumentId = Column(
        UNIQUEIDENTIFIER, ForeignKey("Documents.Id"), nullable=False, index=True
    )
    Score = Column(Float, nullable=False, default=0.0)
    Summary = Column(String, nullable=False, default="")
    Details = Column(String, nullable=True)  # JSON string
    Status = Column(Integer, nullable=False, default=0)  # AnalysisStatus enum
    AnalyzedAt = Column(DateTime, nullable=False, default=datetime.utcnow)

    document = relationship("Document", back_populates="compliance_analyses")


class AuditLog(Base):
    __tablename__ = "AuditLogs"

    Id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    UserId = Column(String(200), nullable=False)
    Action = Column(String(200), nullable=False)
    EntityType = Column(String(200), nullable=False)
    EntityId = Column(String(200), nullable=False)
    Timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    Details = Column(String, nullable=True)  # JSON string


class User(Base):
    """Role values: Admin=0, Analyst=1, Viewer=2."""

    __tablename__ = "Users"

    Id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    EntraObjectId = Column(String(200), nullable=False, unique=True)
    DisplayName = Column(String(500), nullable=False)
    Email = Column(String(500), nullable=False)
    Role = Column(Integer, nullable=False, default=2)  # UserRole enum
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)

    user_queries = relationship("UserQuery", back_populates="user")


class Agent(Base):
    __tablename__ = "Agents"

    Id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    Name = Column(String(200), nullable=False)
    TaskType = Column(String(200), nullable=False)
    IsActive = Column(Boolean, nullable=False, default=True)

    processed_queries = relationship("UserQuery", back_populates="agent")


class UserQuery(Base):
    __tablename__ = "UserQueries"

    Id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    UserId = Column(UNIQUEIDENTIFIER, ForeignKey("Users.Id"), nullable=False)
    Question = Column(String, nullable=False)
    Response = Column(String, nullable=True)
    AgentId = Column(UNIQUEIDENTIFIER, ForeignKey("Agents.Id"), nullable=True)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User", back_populates="user_queries")
    agent = relationship("Agent", back_populates="processed_queries")


class AiRequest(Base):
    __tablename__ = "AiRequests"

    Id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    UserQueryId = Column(
        UNIQUEIDENTIFIER, ForeignKey("UserQueries.Id"), nullable=True
    )
    Question = Column(String, nullable=False)
    Response = Column(String, nullable=True)
    CreatedAt = Column(DateTime, nullable=False, default=datetime.utcnow)

    user_query = relationship("UserQuery")
    context_segments = relationship("AiRequestSegment", back_populates="ai_request")


class AiRequestSegment(Base):
    __tablename__ = "AiRequestSegments"

    AiRequestId = Column(
        UNIQUEIDENTIFIER, ForeignKey("AiRequests.Id"), primary_key=True
    )
    TextSegmentId = Column(
        UNIQUEIDENTIFIER, ForeignKey("TextSegments.Id"), primary_key=True
    )
    RelevanceScore = Column(Float, nullable=True)

    ai_request = relationship("AiRequest", back_populates="context_segments")
    text_segment = relationship("TextSegment", back_populates="ai_request_segments")
