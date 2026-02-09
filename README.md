# TOS Upload Service

火山云对象存储 (TOS) 高性能上传服务 - 基于 FastAPI 的容器化微服务。

---

## 目录

- [性能特性](#-性能特性)
- [快速开始](#-快速开始)
- [详细部署指南](#-详细部署指南)
- [API 接口](#-api-接口)
- [环境变量](#-环境变量)
- [项目结构](#-项目结构)

---

## ⚡ 性能特性

| 优化项 | 描述 |
|--------|------|
| **异步处理** | 所有上传操作使用 async/await，非阻塞 I/O |
| **线程池** | 10 个工作线程并行处理 TOS SDK 操作 |
| **连接复用** | TOS 客户端单例模式，连接池化 |
| **批量上传** | 支持最多 10 张图片并发上传 |
| **GZip 压缩** | 响应体自动压缩 (>1KB) |
| **缓存机制** | 健康检查状态缓存 30 秒 |
| **多 Worker** | 生产环境 4 个 Uvicorn worker + uvloop |

---

## 🚀 快速开始

```bash
# 1. 克隆项目
git clone <repository-url>
cd ToSService

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际的 TOS AK/SK 和 API Key

# 3. Docker 一键部署
docker-compose up -d --build

# 4. 验证服务
curl http://localhost:8001/api/v1/health
```

---

## 📦 详细部署指南

### 方式一：Docker Compose 部署 (推荐)

#### 前置条件

- Docker >= 20.10
- Docker Compose >= 2.0
- 火山引擎 TOS 访问凭证 (AK/SK)

#### 步骤 1: 准备配置文件

```bash
# 复制环境变量模板
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# TOS 配置 (必填)
TOS_REGION=ap-southeast-1
TOS_ENDPOINT=tos-ap-southeast-1.volces.com
TOS_BUCKET_NAME=your-bucket-name
TOS_ACCESS_KEY=your-access-key        # 火山引擎控制台获取
TOS_SECRET_KEY=your-secret-key        # 火山引擎控制台获取
TOS_PUBLIC_DOMAIN=your-bucket.tos-ap-southeast-1.volces.com

# 服务配置 (必填)
API_KEY=your-service-api-key          # 自定义 API Key，用于客户端认证

# 可选配置
MAX_FILE_SIZE_MB=10
LOG_LEVEL=INFO
```

#### 步骤 2: 构建并启动服务

```bash
# 构建镜像并启动
docker-compose up -d --build

# 查看启动日志
docker-compose logs -f

# 预期输出:
# tos-upload-service | Starting TOS Upload Service v1.0.0
# tos-upload-service | TOS Endpoint: tos-ap-southeast-1.volces.com
# tos-upload-service | TOS Bucket: your-bucket-name
```

#### 步骤 3: 验证服务状态

```bash
# 健康检查
curl http://localhost:8001/api/v1/health

# 预期响应:
# {"status":"healthy","service":"TOS Upload Service","version":"1.0.0","tos_connection":"ok",...}

# 查看 API 文档
open http://localhost:8001/docs
```

#### 步骤 4: 常用运维命令

```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看容器状态
docker-compose ps

# 查看实时日志
docker-compose logs -f --tail=100

# 更新服务 (代码修改后)
docker-compose up -d --build
```

---

### 方式二：本地开发部署

#### 前置条件

- Python >= 3.10
- pip

#### 步骤 1: 创建虚拟环境

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# macOS/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
```

#### 步骤 2: 安装依赖

```bash
pip install -r requirements.txt
```

#### 步骤 3: 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入实际配置
```

#### 步骤 4: 启动开发服务器

```bash
# 开发模式 (热重载)
uvicorn app.main:app --reload --port 8001

# 或者生产模式
uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 4
```

---

### 方式三：Kubernetes 部署

#### 创建 Secret

```bash
kubectl create secret generic tos-secrets \
  --from-literal=TOS_ACCESS_KEY=your-ak \
  --from-literal=TOS_SECRET_KEY=your-sk \
  --from-literal=API_KEY=your-api-key
```

#### 部署 Deployment

```yaml
# k8s-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tos-upload-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: tos-upload-service
  template:
    metadata:
      labels:
        app: tos-upload-service
    spec:
      containers:
      - name: tos-upload-service
        image: tos-upload-service:latest
        ports:
        - containerPort: 8001
        envFrom:
        - secretRef:
            name: tos-secrets
        env:
        - name: TOS_REGION
          value: "ap-southeast-1"
        - name: TOS_ENDPOINT
          value: "tos-ap-southeast-1.volces.com"
        - name: TOS_BUCKET_NAME
          value: "your-bucket"
        livenessProbe:
          httpGet:
            path: /api/v1/health/live
            port: 8001
          initialDelaySeconds: 10
          periodSeconds: 15
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: 8001
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

```bash
kubectl apply -f k8s-deployment.yaml
```

---

## 📡 API 接口

详细的 API 文档请参阅 [API_REFERENCE.md](./API_REFERENCE.md)

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/v1/upload/base64` | Base64 图片上传 |
| POST | `/api/v1/upload/image` | Multipart 文件上传 |
| POST | `/api/v1/upload/batch` | 批量并发上传 |
| GET | `/api/v1/health` | 完整健康检查 |
| GET | `/api/v1/health/live` | K8s liveness 探针 |
| GET | `/api/v1/health/ready` | K8s readiness 探针 |

---

## ⚙️ 环境变量

| 变量名 | 必填 | 描述 | 默认值 |
|--------|------|------|--------|
| `TOS_REGION` | ✅ | TOS 区域 | `ap-southeast-1` |
| `TOS_ENDPOINT` | ✅ | TOS 端点 | `tos-ap-southeast-1.volces.com` |
| `TOS_BUCKET_NAME` | ✅ | 存储桶名称 | - |
| `TOS_ACCESS_KEY` | ✅ | 访问密钥 | - |
| `TOS_SECRET_KEY` | ✅ | 密钥 | - |
| `TOS_PUBLIC_DOMAIN` | ✅ | 公网域名 | - |
| `API_KEY` | ✅ | 服务 API Key | - |
| `MAX_FILE_SIZE_MB` | ❌ | 最大文件大小 | `10` |
| `LOG_LEVEL` | ❌ | 日志级别 | `INFO` |

---

## 📁 项目结构

```
ToSService/
├── app/
│   ├── main.py           # FastAPI 入口 + 中间件配置
│   ├── config.py         # Pydantic Settings 配置管理
│   ├── models.py         # 请求/响应数据模型
│   ├── tos_client.py     # 高性能 TOS 客户端封装
│   ├── dependencies.py   # API Key 认证依赖
│   ├── exceptions.py     # 自定义异常 + 处理器
│   └── routers/
│       ├── health.py     # 健康检查路由
│       └── upload.py     # 上传路由
├── tests/                # 单元测试
├── Dockerfile            # 生产优化镜像
├── docker-compose.yml    # 容器编排
├── requirements.txt      # Python 依赖
├── .env.example          # 环境变量模板
├── API_REFERENCE.md      # API 详细文档
└── README.md             # 本文档
```

---

## 📄 许可证

MIT License
