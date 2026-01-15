"""
Common 模块

提供通用功能模块，包括配置管理、日志、数据库、存储等。
"""

from .config import (
    ConfigManager,
    ConfigError,
    get_config_manager,
    load_all_configs,
    AgentConfig,
    DifyConfig,
    StorageConfig,
    VectorDBConfig,
    TestEngineConfig,
    WebConfig,
    DefaultConfig,
)

from .logger import (
    Logger,
    get_logger,
    init_logger,
    debug,
    info,
    warning,
    error,
    critical,
    exception,
)

from .storage import (
    StorageManager,
    StorageError,
    get_storage_manager,
)

from .database import (
    Database,
    DatabaseError,
    get_database,
    TaskStatus,
    TaskType,
)

from .vectordb import (
    VectorDB,
    VectorDBError,
    get_vector_db,
)

from .dify_client import (
    DifyClient,
    DifyAPIError,
)

from .memory import (
    MemoryManager,
    MemoryError,
    WorkingMemory,
    PersistentMemory,
    get_memory_manager,
)

from .test_models import (
    TestEngine,
    TestCase,
    TestResult,
    Request,
    Response,
    Assertion,
    AssertionResult,
    AssertionType,
    AssertionOperator,
    TestCaseStatus,
    TestSuite,
    TestReport,
    ProtocolAdapter,
    create_simple_testcase,
    calculate_pass_rate,
)

from .engines import (
    RequestsEngine,
    HttpRunnerEngine,
)

from .report_generator import (
    ReportGenerator,
)

__all__ = [
    # Config
    'ConfigManager',
    'ConfigError',
    'get_config_manager',
    'load_all_configs',
    'AgentConfig',
    'DifyConfig',
    'StorageConfig',
    'VectorDBConfig',
    'TestEngineConfig',
    'WebConfig',
    'DefaultConfig',
    # Logger
    'Logger',
    'get_logger',
    'init_logger',
    'debug',
    'info',
    'warning',
    'error',
    'critical',
    'exception',
    # Storage
    'StorageManager',
    'StorageError',
    'get_storage_manager',
    # Database
    'Database',
    'DatabaseError',
    'get_database',
    'TaskStatus',
    'TaskType',
    # VectorDB
    'VectorDB',
    'VectorDBError',
    'get_vector_db',
    # Dify Client
    'DifyClient',
    'DifyAPIError',
    # Memory
    'MemoryManager',
    'MemoryError',
    'WorkingMemory',
    'PersistentMemory',
    'get_memory_manager',
    # Test Models
    'TestEngine',
    'TestCase',
    'TestResult',
    'Request',
    'Response',
    'Assertion',
    'AssertionResult',
    'AssertionType',
    'AssertionOperator',
    'TestCaseStatus',
    'TestSuite',
    'TestReport',
    'ProtocolAdapter',
    'create_simple_testcase',
    'calculate_pass_rate',
    # Test Engines
    'RequestsEngine',
    'HttpRunnerEngine',
    # Report Generator
    'ReportGenerator',
]
