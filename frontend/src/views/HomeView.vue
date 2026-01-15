<template>
  <div class="home">
    <el-card class="welcome-card">
      <h2>🎯 欢迎使用 MCP 接口测试智能体</h2>
      <p>基于 MCP 协议的智能化接口测试自动化解决方案</p>
      
      <el-row :gutter="20" class="feature-row">
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>
              <el-icon><Document /></el-icon>
              <span>文档解析</span>
            </template>
            <p>支持 OpenAPI、Swagger、JSON、YAML 等多种格式</p>
          </el-card>
        </el-col>
        
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>
              <el-icon><Magic /></el-icon>
              <span>AI 生成</span>
            </template>
            <p>基于 Dify API 智能生成测试用例</p>
          </el-card>
        </el-col>
        
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>
              <el-icon><Lightning /></el-icon>
              <span>自动执行</span>
            </template>
            <p>支持并发执行、实时监控、断点续传</p>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
    
    <el-card class="quick-start">
      <template #header>
        <h3>🚀 快速开始</h3>
      </template>
      
      <el-steps :active="0" align-center>
        <el-step title="上传文档" description="上传接口文档文件" />
        <el-step title="生成用例" description="AI 自动生成测试用例" />
        <el-step title="执行测试" description="并发执行测试" />
        <el-step title="查看报告" description="下载测试报告" />
      </el-steps>
      
      <div class="action-buttons">
        <div class="upload-wrapper">
          <el-upload
            action="/api/upload"
            :on-success="handleUploadSuccess"
            :show-file-list="false"
            accept=".json,.yaml,.yml,.doc,.docx">
            <el-button type="primary" size="large">
              <el-icon><Upload /></el-icon>
              上传文档开始测试
            </el-button>
          </el-upload>
          <div class="upload-tips">
            <el-text size="small" type="info">
              支持格式：OpenAPI/Swagger (.json/.yaml)、Word文档 (.doc/.docx)
            </el-text>
          </div>
        </div>
        
        <el-button size="large" @click="$router.push('/tasks')">
          <el-icon><List /></el-icon>
          查看任务列表
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import api from '@/api'

const router = useRouter()

const handleUploadSuccess = async (response) => {
  if (response.success) {
    const filePath = response.data.file_path
    const fileName = filePath.split('/').pop()
    const isWord = fileName.endsWith('.doc') || fileName.endsWith('.docx')
    
    // Word文档需要先解析再创建任务
    if (isWord) {
      ElMessage.info('正在解析Word文档，请稍候...')
    }
    
    try {
      const result = await api.createTask({
        task_type: 'api_test',
        document_path: filePath,
        config: {
          test_engine: 'requests',
          parallel_execution: true,
          document_format: isWord ? 'word' : 'auto'
        }
      })
      
      ElMessage.success('任务创建成功！')
      router.push(`/tasks/${result.task_id}`)
    } catch (error) {
      ElMessage.error('任务创建失败：' + error.message)
    }
  }
}
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
}

.welcome-card {
  margin-bottom: 20px;
  text-align: center;
}

.welcome-card h2 {
  margin: 0 0 10px 0;
  color: #667eea;
}

.feature-row {
  margin-top: 30px;
}

.feature-row .el-card {
  text-align: center;
}

.feature-row :deep(.el-card__header) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  font-weight: bold;
}

.quick-start {
  margin-top: 20px;
}

.action-buttons {
  display: flex;
  justify-content: center;
  gap: 20px;
  margin-top: 40px;
}

.upload-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.upload-tips {
  text-align: center;
}
</style>
