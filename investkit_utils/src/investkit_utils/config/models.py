"""InvestKit 配置模型

使用 Pydantic 定义配置结构，提供类型安全和验证。
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from investkit_utils.utils.data_utils import deep_merge

DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_BACKUP_COUNT = 5


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LoggingFormat(str, Enum):
    JSON = "json"
    TEXT = "text"


class DatabaseType(str, Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


class CacheType(str, Enum):
    MEMORY = "memory"
    REDIS = "redis"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class AppConfig(BaseModel):
    name: str = "investkit-app"
    version: str = "1.0.0"
    debug: bool = False
    environment: Environment = Environment.DEVELOPMENT


class LoggingOutputConfig(BaseModel):
    console: bool = True
    file: bool = False
    path: str = "logs/app.log"


class LoggingRotationConfig(BaseModel):
    enabled: bool = True
    max_bytes: int = DEFAULT_LOG_MAX_BYTES
    backup_count: int = DEFAULT_LOG_BACKUP_COUNT


class LoggingFieldsConfig(BaseModel):
    include_timestamp: bool = True
    include_level: bool = True
    include_module: bool = True
    include_correlation_id: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: LoggingFormat = LoggingFormat.JSON
    output: LoggingOutputConfig = Field(default_factory=LoggingOutputConfig)
    rotation: LoggingRotationConfig = Field(default_factory=LoggingRotationConfig)
    fields: LoggingFieldsConfig = Field(default_factory=LoggingFieldsConfig)

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper


class DatabaseSQLiteConfig(BaseModel):
    path: str = "data/app.db"


class DatabasePostgreSQLConfig(BaseModel):
    host: str = "localhost"
    port: int = 5432
    name: str = "investkit"
    user: str = ""
    password: str = ""


class DatabasePoolConfig(BaseModel):
    size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30


class DatabaseConfig(BaseModel):
    type: DatabaseType = DatabaseType.SQLITE
    sqlite: DatabaseSQLiteConfig = Field(default_factory=DatabaseSQLiteConfig)
    postgresql: DatabasePostgreSQLConfig = Field(default_factory=DatabasePostgreSQLConfig)
    pool: DatabasePoolConfig = Field(default_factory=DatabasePoolConfig)


class CacheRedisConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""


class CacheConfig(BaseModel):
    enabled: bool = True
    type: CacheType = CacheType.MEMORY
    ttl: int = 3600
    redis: CacheRedisConfig = Field(default_factory=CacheRedisConfig)


class ApiCorsConfig(BaseModel):
    enabled: bool = True
    origins: list[str] = Field(default_factory=lambda: ["*"])
    methods: list[str] = Field(default_factory=lambda: ["GET", "POST", "PUT", "DELETE"])
    headers: list[str] = Field(default_factory=lambda: ["*"])


class ApiRateLimitConfig(BaseModel):
    enabled: bool = True
    requests_per_minute: int = 60


class ApiDocsConfig(BaseModel):
    enabled: bool = True
    path: str = "/docs"
    redoc_path: str = "/redoc"


class ApiConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    cors: ApiCorsConfig = Field(default_factory=ApiCorsConfig)
    rate_limit: ApiRateLimitConfig = Field(default_factory=ApiRateLimitConfig)
    docs: ApiDocsConfig = Field(default_factory=ApiDocsConfig)


class LLMOpenAIConfig(BaseModel):
    api_key: str = ""
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000


class LLMAnthropicConfig(BaseModel):
    api_key: str = ""
    model: str = "claude-3-opus-20240229"
    temperature: float = 0.7
    max_tokens: int = 2000


class LLMOllamaConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "llama3"
    temperature: float = 0.7


class LLMConfig(BaseModel):
    default_provider: LLMProvider = LLMProvider.OLLAMA
    openai: LLMOpenAIConfig = Field(default_factory=LLMOpenAIConfig)
    anthropic: LLMAnthropicConfig = Field(default_factory=LLMAnthropicConfig)
    ollama: LLMOllamaConfig = Field(default_factory=LLMOllamaConfig)


class DataSourceAkshareConfig(BaseModel):
    enabled: bool = True
    retry_count: int = 3
    retry_delay: int = 1
    timeout: int = 30


class DataSourceAlphaVantageConfig(BaseModel):
    enabled: bool = False
    api_key: str = ""
    rate_limit: int = 5


class DataSourcesConfig(BaseModel):
    akshare: DataSourceAkshareConfig = Field(default_factory=DataSourceAkshareConfig)
    alpha_vantage: DataSourceAlphaVantageConfig = Field(default_factory=DataSourceAlphaVantageConfig)


class MLFeaturesConfig(BaseModel):
    count: int = 51
    cache_enabled: bool = True


class MLTrainingConfig(BaseModel):
    test_size: float = 0.2
    cross_validation: int = 5
    random_state: int = 42


class MLPredictionConfig(BaseModel):
    batch_size: int = 100
    confidence_threshold: float = 0.6


class MLConfig(BaseModel):
    model_path: str = "models/"
    features: MLFeaturesConfig = Field(default_factory=MLFeaturesConfig)
    training: MLTrainingConfig = Field(default_factory=MLTrainingConfig)
    prediction: MLPredictionConfig = Field(default_factory=MLPredictionConfig)


class MonitoringMetricsConfig(BaseModel):
    enabled: bool = True
    port: int = 9090


class MonitoringHealthCheckConfig(BaseModel):
    enabled: bool = True
    path: str = "/health"


class MonitoringTracingConfig(BaseModel):
    enabled: bool = False
    sample_rate: float = 0.1


class MonitoringConfig(BaseModel):
    metrics: MonitoringMetricsConfig = Field(default_factory=MonitoringMetricsConfig)
    health_check: MonitoringHealthCheckConfig = Field(default_factory=MonitoringHealthCheckConfig)
    tracing: MonitoringTracingConfig = Field(default_factory=MonitoringTracingConfig)


class SecurityAPIKeyConfig(BaseModel):
    header_name: str = "X-API-Key"
    enabled: bool = False


class SecurityJWTConfig(BaseModel):
    enabled: bool = False
    secret: str = ""
    algorithm: str = "HS256"
    expire_minutes: int = 60


class SecurityConfig(BaseModel):
    api_key: SecurityAPIKeyConfig = Field(default_factory=SecurityAPIKeyConfig)
    jwt: SecurityJWTConfig = Field(default_factory=SecurityJWTConfig)


class Config(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    api: ApiConfig = Field(default_factory=ApiConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    data_sources: DataSourcesConfig = Field(default_factory=DataSourcesConfig)
    ml: MLConfig = Field(default_factory=MLConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    model_config = {"extra": "allow"}

    @classmethod
    def from_yaml(cls, path: str | Path) -> Config:
        from investkit_utils.config.loader import ConfigLoader

        return ConfigLoader.load_from_file(path)

    def merge(self, other: dict[str, Any] | Config) -> Config:
        if isinstance(other, Config):
            other = other.model_dump()

        current = self.model_dump()
        merged = deep_merge(current, other)
        return Config(**merged)
