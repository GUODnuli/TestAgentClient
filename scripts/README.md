# 模型管理说明

## 嵌入模型 (Embedding Models)

本项目使用以下嵌入模型，**无需提交到 Git**：

| 模型 | 用途 | 缓存位置 | 大小 |
|------|------|----------|------|
| all-MiniLM-L6-v2 (ONNX) | ChromaDB 向量检索 | `~/.cache/chroma/onnx_models/` | ~86 MB |
| all-MiniLM-L6-v2 | sentence-transformers | `~/.cache/huggingface/hub/` | ~90 MB |

## 初始化模型

首次使用或新环境部署时运行：

```bash
python scripts/init_models.py
```

这会自动下载所需模型到系统缓存目录。

## 手动下载

如果自动下载失败，可以手动安装：

```bash
# 安装依赖
pip install chromadb sentence-transformers

# 手动触发下载
python -c "
import chromadb
from chromadb.config import Settings
client = chromadb.Client(Settings(anonymized_telemetry=False))
collection = client.create_collection('test')
collection.add(ids=['1'], documents=['test'])
client.delete_collection('test')
print('ChromaDB model ready')
"

python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
print('SentenceTransformer model ready')
"
```

## 缓存清理

如需清理磁盘空间，可以安全删除：

```bash
# 删除 ChromaDB 缓存
rm -rf ~/.cache/chroma/

# 删除 HuggingFace 缓存
rm -rf ~/.cache/huggingface/
```

下次使用时会自动重新下载。
