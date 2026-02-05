#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
模型初始化脚本

在系统首次部署时运行，预先下载所需的模型文件，避免运行时延迟。

包含：
1. ChromaDB ONNX 嵌入模型 (all-MiniLM-L6-v2)
2. sentence-transformers 嵌入模型

使用方法：
    python scripts/init_models.py
"""

import os
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def init_chromadb_model():
    """
    初始化 ChromaDB 的 ONNX 嵌入模型

    ChromaDB 默认使用 all-MiniLM-L6-v2 的 ONNX 版本，
    首次使用时会自动下载到 ~/.cache/chroma/onnx_models/
    """
    logger.info("Initializing ChromaDB ONNX embedding model...")

    try:
        import chromadb
        from chromadb.config import Settings

        # 创建临时客户端触发模型下载
        client = chromadb.Client(Settings(anonymized_telemetry=False))

        # 创建临时集合并添加文档，触发嵌入模型下载
        collection = client.create_collection(
            name="__init_test__",
            metadata={"hnsw:space": "cosine"}
        )

        # 添加测试文档触发模型加载
        collection.add(
            ids=["test_1"],
            documents=["This is a test document to initialize the embedding model."]
        )

        # 清理
        client.delete_collection("__init_test__")

        logger.info("ChromaDB ONNX model initialized successfully!")
        logger.info("Model location: ~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/")
        return True

    except Exception as e:
        logger.error(f"Failed to initialize ChromaDB model: {e}")
        return False


def init_sentence_transformers_model():
    """
    初始化 sentence-transformers 嵌入模型

    记忆系统使用 sentence-transformers 生成嵌入向量，
    首次使用时会自动下载到 ~/.cache/huggingface/
    """
    logger.info("Initializing sentence-transformers embedding model...")

    try:
        from sentence_transformers import SentenceTransformer

        # 加载模型（首次会下载）
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        model = SentenceTransformer(model_name)

        # 测试编码
        test_embedding = model.encode(["Test sentence for model initialization."])

        logger.info(f"sentence-transformers model initialized successfully!")
        logger.info(f"Model: {model_name}")
        logger.info(f"Embedding dimension: {len(test_embedding[0])}")
        return True

    except ImportError:
        logger.warning("sentence-transformers not installed, skipping...")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize sentence-transformers model: {e}")
        return False


def init_memory_storage():
    """
    初始化记忆系统存储目录
    """
    logger.info("Initializing memory storage directories...")

    storage_path = os.path.join(os.path.dirname(__file__), "..", "storage", "memory")
    storage_path = os.path.abspath(storage_path)

    dirs_to_create = [
        storage_path,
        os.path.join(storage_path, "global"),
        os.path.join(storage_path, "plans"),
    ]

    for dir_path in dirs_to_create:
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Created directory: {dir_path}")

    logger.info("Memory storage initialized successfully!")
    return True


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("TestAgent Model Initialization")
    logger.info("=" * 60)

    success = True

    # 1. 初始化存储目录
    if not init_memory_storage():
        success = False

    # 2. 初始化 ChromaDB 模型
    if not init_chromadb_model():
        success = False

    # 3. 初始化 sentence-transformers 模型
    if not init_sentence_transformers_model():
        success = False

    logger.info("=" * 60)
    if success:
        logger.info("All models initialized successfully!")
        logger.info("The system is ready to use without runtime model downloads.")
    else:
        logger.error("Some models failed to initialize. Please check the logs above.")
        sys.exit(1)

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
