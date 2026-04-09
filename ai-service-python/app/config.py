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
    groq_model: str = "llama-3.3-70b-versatile"

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

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"


settings = Settings()  # type: ignore[call-arg]
