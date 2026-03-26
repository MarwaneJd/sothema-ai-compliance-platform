# System Architecture

## 1. Architecture Overview

The AI Compliance Platform follows a **modular and scalable architecture** designed for enterprise environments.

The system integrates document management platforms, artificial intelligence services, and enterprise authentication mechanisms.

The architecture is composed of five main layers:

1. Client Layer
2. Backend API Layer
3. AI Processing Layer
4. Data Storage Layer
5. External Enterprise Services

---

## 2. High-Level Architecture

Client (React Web Application)
│
▼
ASP.NET Core API
│
▼
Python AI Service (FastAPI)
│
▼
Multi-Agent System
│
├ Document Retrieval Agent
├ Content Analysis Agent
├ Regulatory Compliance Agent
├ Compliance Scoring Agent
├ Explanation Agent
└ Audit Agent
│
├ Vector Database (FAISS)
├ Relational Database
└ SharePoint Document Repository

---

## 3. Client Layer

The client layer consists of a web application built using:

- React
- TypeScript
- TailwindCSS

The frontend allows users to:

- authenticate using Microsoft Entra ID
- search regulatory documents
- ask compliance questions
- view AI-generated analyses
- consult compliance scores
- access audit logs

---

## 4. Backend API Layer

The backend is implemented using **ASP.NET Core**.

This API acts as the **central orchestration layer** of the platform.

Responsibilities include:

- handling HTTP requests
- validating authentication tokens
- managing user roles
- communicating with the AI service
- retrieving documents from SharePoint
- managing compliance data and logs

The backend also ensures secure communication with enterprise services.

---

## 5. SharePoint Integration and Security

SharePoint serves as the **primary document repository** for regulatory and quality documentation.

For security reasons, SharePoint is **not accessed directly by the frontend or the AI service**.

Instead, the ASP.NET Core API acts as a secure gateway between the platform and SharePoint.

### Authentication

User authentication is handled using Microsoft Entra ID through OAuth2 / OpenID Connect.

Authentication flow:

1. The user logs in using Microsoft Entra ID.
2. The system receives an authentication token.
3. The ASP.NET Core API validates the token.
4. The API uses the authenticated identity to access SharePoint.

### SharePoint Access

The API retrieves documents using the **Microsoft Graph API**.

Architecture flow:

User → Frontend → ASP.NET Core API → Microsoft Graph API → SharePoint

This ensures:

- secure access control
- respect of SharePoint permissions
- protection of sensitive pharmaceutical data

Retrieved documents are then sent to the AI service for processing.

---

## 6. AI Processing Layer

The AI processing layer is implemented as a **Python microservice** using FastAPI.

Responsibilities include:

- document ingestion
- text extraction
- embedding generation
- hybrid document retrieval
- orchestration of the RAG pipeline
- multi-agent coordination

The AI service uses **LangGraph** to manage interactions between AI agents.

---

## 7. Hybrid RAG Pipeline

The system uses a **Hybrid Retrieval-Augmented Generation (Hybrid RAG) pipeline**.

Pipeline steps:

1. Document retrieval from SharePoint
2. Text extraction from documents
3. Text segmentation into chunks
4. Embedding generation
5. Storage of embeddings in FAISS
6. Hybrid retrieval (vector search + keyword search)
7. Context aggregation
8. Response generation using Azure OpenAI

This approach improves retrieval accuracy and ensures responses are based on reliable internal documentation.

---

## 8. Multi-Agent System

The AI service includes several specialized agents.

### Document Retrieval Agent
Retrieves documents and relevant sections.

### Content Analysis Agent
Processes document content and prepares data for analysis.

### Regulatory Compliance Agent
Analyzes regulatory requirements within documents.

### Compliance Scoring Agent
Generates compliance scores for analyzed documents.

### Explanation Agent
Provides explanations of AI decisions and references to source documents.

### Audit Agent
Logs system interactions to ensure traceability and auditability.

---

## 9. Data Storage Layer

The platform uses two types of storage systems.

### Vector Database (FAISS)

Stores document embeddings for semantic search.

### Relational Database

Stores:

- user data
- document metadata
- compliance scores
- audit logs
- system metrics

Supported systems:

- Microsoft SQL Server

---

## 10. External Services

The platform integrates with several external enterprise services.

### Microsoft Entra ID

Provides identity management and secure authentication.

### Microsoft SharePoint

Stores regulatory and internal compliance documentation.

### Azure OpenAI Service

Provides large language models used for document analysis and response generation.

---

## 11. Security Architecture

Security mechanisms include:

- authentication through Entra ID
- role-based access control
- secure API communication
- token validation
- audit logging

These mechanisms ensure the protection of sensitive pharmaceutical information.

---

## 12. Scalability and Deployment

The architecture supports scalable deployment using containerized services.

Components that can scale independently include:

- ASP.NET Core API
- AI microservice
- vector database

Deployment can be performed using container platforms such as Docker in cloud or on-premise infrastructure.

---

## 13. Conclusion

The AI Compliance Platform architecture combines enterprise software technologies with advanced artificial intelligence techniques.

By integrating SharePoint document management, Hybrid RAG retrieval, and a multi-agent AI system, the platform provides a powerful solution for intelligent regulatory document analysis in pharmaceutical environments.