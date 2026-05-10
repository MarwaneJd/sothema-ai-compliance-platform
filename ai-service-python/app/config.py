from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AI_SERVICE_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Security
    api_key: str

    # Database (SQL Server via ODBC)
    database_connection_string: str

    # LLM Provider: "azure" or "groq"
    llm_provider: str = "azure"

    # Azure OpenAI (used when llm_provider == "azure")
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-06-01"
    azure_openai_chat_deployment: str = "gpt-4o"

    # Groq (used when llm_provider == "groq")
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"  # legacy; reasoning-tier default
    groq_fast_model: str = "llama-3.3-70b-versatile"  # fast-tier; same model in dev

    # Tier-specific Azure deployments (prod). In dev (Groq) both tiers share the same model.
    azure_openai_chat_deployment_fast: str = "gpt-4o-mini"

    # Ollama local (used when llm_provider == "ollama")
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen3.5:4b"

    # Embedding (local sentence-transformers model)
    embedding_model_name: str = "all-MiniLM-L6-v2"
    embedding_dimensions: int = 384

    # FAISS
    faiss_index_path: str = "data/faiss_indexes"

    # RAG Configuration
    chunk_size: int = 512
    chunk_overlap: int = 50
    rrf_k: int = 60
    top_k_results: int = 10

    # Cross-encoder reranker (Phase 1)
    enable_reranker: bool = True
    # Multilingual MiniLM (FR/AR/EN-trained on mMARCO). ~14× faster on CPU than
    # bge-reranker-v2-m3 with similar relative ranking quality — usable inside
    # the Fast-mode <3s SLA on Docker-for-Mac. Swap back to bge-reranker-v2-m3
    # if you move to GPU and want maximum quality.
    reranker_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    reranker_fetch_multiplier: int = 4  # fetch top_k * N candidates, rerank to top_k
    reranker_max_length: int = 256  # token cap per (query, candidate) pair — keeps CPU latency bounded

    # Multi-query rewriting (Phase 2)
    enable_multi_query: bool = True
    multi_query_count: int = 3  # number of expansion variants per query
    query_expansion_timeout_ms: int = 800  # fallback to original-query-only on timeout
    query_expansion_cache_size: int = 2048

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


settings = Settings()  # type: ignore[call-arg]
