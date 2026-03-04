# TOS Upload Service

火山云对象存储 (TOS) 高性能上传服务 — 基于 FastAPI 的容器化微服务。

---

## 目录

- [性能特性](#-性能特性)
- [快速开始](#-快速开始)
- [容器化部署 (Docker)](#-容器化部署-docker)
- [本地开发](#-本地开发)
- [Kubernetes 部署](#-kubernetes-部署)
- [API 接口](#-api-接口)
- [环境变量](#-环境变量)
- [项目结构](#-项目结构)
- [常见问题排查](#-常见问题排查)

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
| **Request ID 追踪** | 全链路日志追踪，自动注入 `X-Request-ID` |

---

## 🚀 快速开始

> **前置条件：** Docker >= 20.10 & Docker Compose V2

```bash
# 1. 克隆项目
git clone <repository-url>
cd ToSService

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际的 TOS AK/SK 和 API Key

# 3. 一键启动
make up

# 4. 验证服务
make health
```

启动成功后访问：

| 地址 | 说明 |
|------|------|
| <http://localhost:10086/docs> | Swagger 交互文档 |
| <http://localhost:10086/redoc> | ReDoc 文档 |
| <http://localhost:10086/api/v1/health> | 健康检查 |

---

## 🐳 容器化部署 (Docker)

### 架构概览

```text
┌─────────────────────────────────────────────────────┐
│  Docker Container (tos-upload-service)               │
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │  Uvicorn (4 workers, uvloop + httptools)     │    │
│  │  └─ FastAPI App                              │    │
│  │     ├─ /api/v1/upload/*   ← 上传接口         │    │
│  │     ├─ /api/v1/health/*   ← 健康探针         │    │
│  │     └─ ThreadPoolExecutor (10 workers)       │    │
│  │        └─ TOS SDK (connection pooling)       │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
│  Volume: /app/logs  →  ./logs (宿主机)              │
│  Port:   10086      →  ${SERVICE_PORT:-10086}        │
└─────────────────────────────────────────────────────┘
```

### 步骤 1：准备环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入以下**必填**项：

```bash
# TOS 凭证 (从火山引擎控制台获取)
TOS_ACCESS_KEY=AKLTxxxxxxxxxxxxxxxx
TOS_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxx

# 服务认证 (自定义一个强密码作为 API Key)
API_KEY=your-secure-api-key-here
```

其余配置均有默认值，可按需修改（参见 [环境变量](#-环境变量)）。

### 步骤 2：构建并启动

```bash
# 方式 A：使用 Makefile (推荐)
make up          # 构建镜像 + 后台启动

# 方式 B：直接使用 docker compose
docker compose up -d --build
```

**首次构建** 日志示例：

```text
[+] Building 15.2s (12/12) FINISHED
 => [builder] pip install ... requirements.txt
 => [runtime] COPY --from=builder /install /usr/local
 => ...
[+] Running 1/1
 ✔ Container tos-upload-service  Started

✅ 服务已启动  →  http://localhost:10086/docs
```

### 步骤 3：验证服务

```bash
# 快捷方式
make health

# 或手动 curl
curl -s http://localhost:10086/api/v1/health | python3 -m json.tool
```

预期输出：

```json
{
    "status": "healthy",
    "service": "TOS Upload Service",
    "version": "1.0.0",
    "tos_connection": "ok",
    "timestamp": "2026-03-04T02:00:00.000000Z"
}
```

### 步骤 4：测试上传

```bash
# Base64 上传测试 (1x1 白色 PNG)
curl -X POST http://localhost:10086/api/v1/upload/base64 \
     -H "X-API-Key: ${API_KEY}" \
     -H "Content-Type: application/json" \
     -d '{
       "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
       "format": "png",
       "prefix": "test/"
     }'

# 文件上传测试
curl -X POST http://localhost:10086/api/v1/upload/image \
     -H "X-API-Key: ${API_KEY}" \
     -F "file=@/path/to/image.jpg" \
     -F "prefix=test/"
```

### 日常运维命令

使用 `make help` 查看所有可用命令：

```bash
make help         # 显示所有命令
make up           # 构建并启动
make down         # 停止容器
make restart      # 重启服务
make logs         # 查看实时日志
make status       # 查看容器状态
make health       # 执行健康检查
make clean        # 停止并清理镜像、日志
```

也可以直接使用 `docker compose`：

```bash
docker compose logs -f --tail=200   # 实时日志
docker compose ps                   # 容器状态
docker compose restart              # 重启
docker compose down                 # 停止
docker compose up -d --build        # 更新后重新部署
```

### Dockerfile 优化说明

本项目使用 **多阶段构建 (Multi-stage Build)**，显著减小最终镜像体积：

| 阶段 | 用途 | 说明 |
|------|------|------|
| `builder` | 安装 Python 依赖 | 仅存在于构建过程，不进入最终镜像 |
| `runtime` | 运行应用 | 仅包含最终依赖 + 应用代码 |

其他安全与性能优化：

- **非 root 用户** (`appuser`) 运行
- **HEALTHCHECK** 内置健康检查
- **资源限制**：CPU ≤ 1 核，内存 ≤ 512MB（`docker-compose.yml` 配置）
- **日志轮转**：Docker 日志限制 10MB × 5 个文件
- **并发限制**：最大 1000 并发，10000 请求后自动重启 Worker

---

## 💻 本地开发

```bash
# 1. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env

# 4. 启动开发服务器 (热重载)
make dev
# 或直接：uvicorn app.main:app --reload --port 10086

# 5. 运行测试
make test
# 或直接：python -m pytest tests/ -v
```

---

## ☸️ Kubernetes 部署

### 创建 Secret

```bash
kubectl create secret generic tos-secrets \
  --from-literal=TOS_ACCESS_KEY=your-ak \
  --from-literal=TOS_SECRET_KEY=your-sk \
  --from-literal=API_KEY=your-api-key
```

### Deployment 示例

```yaml
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
        - containerPort: 10086
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
            port: 10086
          initialDelaySeconds: 10
          periodSeconds: 15
        readinessProbe:
          httpGet:
            path: /api/v1/health/ready
            port: 10086
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

### Service 示例

```yaml
apiVersion: v1
kind: Service
metadata:
  name: tos-upload-service
spec:
  type: ClusterIP
  selector:
    app: tos-upload-service
  ports:
  - port: 80
    targetPort: 10086
    protocol: TCP
```

```bash
kubectl apply -f k8s-deployment.yaml
kubectl apply -f k8s-service.yaml
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
| `SERVICE_PORT` | ❌ | 宿主机映射端口 | `10086` |
| `MAX_FILE_SIZE_MB` | ❌ | 最大文件大小 | `10` |
| `LOG_LEVEL` | ❌ | 日志级别 | `INFO` |

---

## 📁 项目结构

```
ToSService/
├── app/
│   ├── main.py              # FastAPI 入口 + 请求 ID 中间件
│   ├── config.py            # Pydantic Settings 配置管理
│   ├── models.py            # 请求/响应数据模型
│   ├── tos_client.py        # 高性能 TOS 客户端封装
│   ├── dependencies.py      # API Key 认证依赖
│   ├── exceptions.py        # 自定义异常 + 处理器
│   ├── logging_config.py    # 日志配置 (Request ID 追踪)
│   └── routers/
│       ├── health.py        # 健康检查路由
│       └── upload.py        # 上传路由
├── tests/                   # 单元测试
├── Dockerfile               # 多阶段生产镜像
├── docker-compose.yml       # 容器编排
├── Makefile                 # 运维快捷命令
├── requirements.txt         # Python 依赖
├── .env.example             # 环境变量模板
├── API_REFERENCE.md         # API 详细文档
└── README.md                # 本文档
```

---

## 🔧 常见问题排查

### 容器启动失败

```bash
# 查看启动日志
docker compose logs tos-upload-service

# 常见原因
# 1. .env 文件不存在 → cp .env.example .env
# 2. TOS_ACCESS_KEY / TOS_SECRET_KEY 为空 → 填入真实凭证
# 3. 端口被占用 → 修改 .env 中的 SERVICE_PORT
```

### 健康检查返回 `tos_connection: error`

```bash
# 检查 TOS 凭证是否正确
curl -s http://localhost:10086/api/v1/health | python3 -m json.tool

# 验证 TOS 网络连通性
docker compose exec tos-upload-service \
  curl -sf https://${TOS_ENDPOINT} -o /dev/null -w "%{http_code}" && echo " OK" || echo " FAIL"
```

### 日志文件没有生成

```bash
# 确保 logs 目录存在且有写权限
ls -la logs/

# 检查容器内权限
docker compose exec tos-upload-service ls -la /app/logs/
```

### 上传返回 401

```bash
# 确认 API Key 一致
echo "API_KEY in .env: $(grep API_KEY .env)"

# 请求时携带 X-API-Key 头
curl -H "X-API-Key: YOUR_KEY" http://localhost:10086/api/v1/upload/base64 ...
```

---

## 📄 许可证

MIT License
