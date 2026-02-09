# TOS Upload Service API 接口文档

> **版本**: v1.0.0  
> **基础路径**: `http://localhost:8001`  
> **在线文档**: <http://localhost:8001/docs> (Swagger UI)

---

## 目录

- [认证方式](#认证方式)
- [通用响应格式](#通用响应格式)
- [错误码定义](#错误码定义)
- [接口详情](#接口详情)
  - [Base64 图片上传](#1-base64-图片上传)
  - [文件上传](#2-文件上传)
  - [批量上传](#3-批量上传)
  - [健康检查](#4-健康检查)
  - [存活探针](#5-存活探针)
  - [就绪探针](#6-就绪探针)

---

## 认证方式

所有上传接口 (`/api/v1/upload/*`) 需要在请求头中携带 API Key：

```http
X-API-Key: <your-api-key>
```

健康检查接口无需认证。

---

## 通用响应格式

### 成功响应

```json
{
  "success": true,
  "code": 0,
  "message": "Upload successful",
  "data": { ... }
}
```

### 失败响应

```json
{
  "success": false,
  "code": 40001,
  "message": "Invalid file format. Supported: JPEG, PNG, WEBP",
  "data": null
}
```

---

## 错误码定义

| 错误码 | HTTP 状态码 | 描述 | 可能原因 |
|--------|-------------|------|----------|
| `0` | 200 | 成功 | - |
| `40001` | 400 | 无效的文件格式 | 文件不是 JPEG/PNG/WEBP 格式 |
| `40002` | 400 | 文件大小超出限制 | 文件超过 10MB |
| `40003` | 400 | Base64 解码失败 | Base64 字符串格式错误 |
| `40101` | 401 | 缺少 API Key | 请求头未携带 X-API-Key |
| `40102` | 401 | 无效的 API Key | API Key 不正确 |
| `50001` | 500 | TOS 上传失败 | TOS 服务端错误或网络问题 |
| `50002` | 500 | 服务内部错误 | 服务端未知异常 |

---

## 接口详情

---

### 1. Base64 图片上传

上传 Base64 编码的图片数据，适用于移动端客户端。

**请求**

```
POST /api/v1/upload/base64
Content-Type: application/json
X-API-Key: <your-api-key>
```

**请求体**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `image_base64` | string | ✅ | Base64 编码的图片数据（不含 `data:image/...;base64,` 前缀） |
| `format` | string | ❌ | 图片格式：`jpeg` / `png` / `webp`，默认 `jpeg` |
| `prefix` | string | ❌ | 存储路径前缀，默认 `generated/` |
| `quality` | integer | ❌ | 压缩质量 1-100，默认 `90` |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/upload/base64" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "/9j/4AAQSkZJRgABAQAAAQABAAD...",
    "format": "jpeg",
    "prefix": "user_photos/",
    "quality": 90
  }'
```

**成功响应 (200)**

```json
{
  "success": true,
  "code": 0,
  "message": "Upload successful",
  "data": {
    "public_url": "https://bucket.tos-ap-southeast-1.volces.com/user_photos/a1b2c3d4e5f6_20260209_114500.jpg",
    "object_key": "user_photos/a1b2c3d4e5f6_20260209_114500.jpg",
    "etag": "\"d41d8cd98f00b204e9800998ecf8427e\"",
    "size_bytes": 245678,
    "content_type": "image/jpeg",
    "upload_time": "2026-02-09T03:45:00.000Z"
  }
}
```

**错误响应示例**

Base64 解码失败 (400):

```json
{
  "success": false,
  "code": 40003,
  "message": "Failed to decode Base64 data: Invalid padding",
  "data": null
}
```

文件过大 (400):

```json
{
  "success": false,
  "code": 40002,
  "message": "File size exceeds maximum limit of 10MB",
  "data": null
}
```

缺少 API Key (401):

```json
{
  "success": false,
  "code": 40101,
  "message": "Missing API key. Please provide X-API-Key header.",
  "data": null
}
```

---

### 2. 文件上传

通过 Multipart 表单上传图片文件，适用于 Web 端。

**请求**

```
POST /api/v1/upload/image
Content-Type: multipart/form-data
X-API-Key: <your-api-key>
```

**请求参数**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `file` | File | ✅ | 图片文件，支持 JPEG/PNG/WEBP，最大 10MB |
| `prefix` | string | ❌ | 存储路径前缀，默认 `generated/` |
| `quality` | integer | ❌ | 压缩质量 1-100，默认 `90` |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/upload/image" \
  -H "X-API-Key: your-api-key" \
  -F "file=@/path/to/photo.jpg" \
  -F "prefix=avatars/" \
  -F "quality=85"
```

**成功响应 (200)**

```json
{
  "success": true,
  "code": 0,
  "message": "Upload successful",
  "data": {
    "public_url": "https://bucket.tos-ap-southeast-1.volces.com/avatars/c3d4e5f6a1b2_20260209_114530.jpg",
    "object_key": "avatars/c3d4e5f6a1b2_20260209_114530.jpg",
    "etag": "\"e99a18c428cb38d5f260853678922e03\"",
    "size_bytes": 102400,
    "content_type": "image/jpeg",
    "upload_time": "2026-02-09T03:45:30.000Z"
  }
}
```

**错误响应示例**

无效文件格式 (400):

```json
{
  "success": false,
  "code": 40001,
  "message": "Invalid content type: text/plain. Supported: JPEG, PNG, WEBP",
  "data": null
}
```

文件格式验证失败 (400):

```json
{
  "success": false,
  "code": 40001,
  "message": "Unable to detect valid image format from file content",
  "data": null
}
```

---

### 3. 批量上传

并发上传多张 Base64 编码的图片，最多支持 10 张。

**请求**

```
POST /api/v1/upload/batch
Content-Type: application/json
X-API-Key: <your-api-key>
```

**请求体**

数组，每个元素结构同 Base64 上传请求：

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `image_base64` | string | ✅ | Base64 编码的图片数据 |
| `format` | string | ❌ | 图片格式，默认 `jpeg` |
| `prefix` | string | ❌ | 存储路径前缀，默认 `generated/` |
| `quality` | integer | ❌ | 压缩质量，默认 `90` |

**请求示例**

```bash
curl -X POST "http://localhost:8001/api/v1/upload/batch" \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "image_base64": "/9j/4AAQSkZJRg...",
      "format": "jpeg",
      "prefix": "batch/"
    },
    {
      "image_base64": "iVBORw0KGgo...",
      "format": "png",
      "prefix": "batch/"
    }
  ]'
```

**成功响应 (200)**

```json
{
  "success": true,
  "code": 0,
  "message": "Successfully uploaded 2 images",
  "data": [
    {
      "public_url": "https://bucket.tos-ap-southeast-1.volces.com/batch/d4e5f6a1b2c3_20260209_114600.jpg",
      "object_key": "batch/d4e5f6a1b2c3_20260209_114600.jpg",
      "etag": "\"abc123...\"",
      "size_bytes": 150000,
      "content_type": "image/jpeg",
      "upload_time": "2026-02-09T03:46:00.000Z"
    },
    {
      "public_url": "https://bucket.tos-ap-southeast-1.volces.com/batch/e5f6a1b2c3d4_20260209_114600.png",
      "object_key": "batch/e5f6a1b2c3d4_20260209_114600.png",
      "etag": "\"def456...\"",
      "size_bytes": 200000,
      "content_type": "image/png",
      "upload_time": "2026-02-09T03:46:00.000Z"
    }
  ]
}
```

**错误响应示例**

超过批量限制 (400):

```json
{
  "success": false,
  "code": 40001,
  "message": "Maximum 10 images per batch upload",
  "data": null
}
```

---

### 4. 健康检查

完整的服务健康检查，包含 TOS 连接状态。

**请求**

```
GET /api/v1/health
```

**响应 (200)**

```json
{
  "status": "healthy",
  "service": "TOS Upload Service",
  "version": "1.0.0",
  "tos_connection": "ok",
  "timestamp": "2026-02-09T03:46:30.000Z"
}
```

**TOS 连接异常时**

```json
{
  "status": "healthy",
  "service": "TOS Upload Service",
  "version": "1.0.0",
  "tos_connection": "error",
  "timestamp": "2026-02-09T03:46:30.000Z"
}
```

> 注意：TOS 连接状态有 30 秒缓存，避免频繁检测。

---

### 5. 存活探针

Kubernetes liveness probe，仅检查服务是否运行。

**请求**

```
GET /api/v1/health/live
```

**响应 (200)**

```json
{
  "status": "alive"
}
```

---

### 6. 就绪探针

Kubernetes readiness probe，检查服务是否可以接收流量。

**请求**

```
GET /api/v1/health/ready
```

**成功响应 (200)**

```json
{
  "status": "ready"
}
```

**未就绪响应 (200)**

```json
{
  "status": "not_ready",
  "reason": "TOS connection failed"
}
```

---

## 响应数据结构

### UploadResult

上传成功后返回的数据结构：

| 字段 | 类型 | 描述 |
|------|------|------|
| `public_url` | string | 公网可访问的 URL |
| `object_key` | string | TOS 对象存储键 |
| `etag` | string | ETag 校验值 |
| `size_bytes` | integer | 文件大小（字节） |
| `content_type` | string | MIME 类型 |
| `upload_time` | string (ISO 8601) | 上传时间 |

---

## 客户端集成示例

### Python

```python
import requests
import base64

# 读取图片并编码
with open("photo.jpg", "rb") as f:
    image_base64 = base64.b64encode(f.read()).decode()

# 上传
response = requests.post(
    "http://localhost:8001/api/v1/upload/base64",
    headers={"X-API-Key": "your-api-key"},
    json={
        "image_base64": image_base64,
        "format": "jpeg",
        "prefix": "uploads/"
    }
)

result = response.json()
if result["success"]:
    print(f"上传成功: {result['data']['public_url']}")
else:
    print(f"上传失败: {result['message']}")
```

### JavaScript (Node.js)

```javascript
const fs = require('fs');
const axios = require('axios');

const imageBase64 = fs.readFileSync('photo.jpg').toString('base64');

axios.post('http://localhost:8001/api/v1/upload/base64', {
    image_base64: imageBase64,
    format: 'jpeg',
    prefix: 'uploads/'
}, {
    headers: { 'X-API-Key': 'your-api-key' }
})
.then(res => {
    if (res.data.success) {
        console.log('上传成功:', res.data.data.public_url);
    }
})
.catch(err => console.error('上传失败:', err.message));
```

### Android (Kotlin)

```kotlin
val bitmap: Bitmap = ... // 获取 Bitmap
val baos = ByteArrayOutputStream()
bitmap.compress(Bitmap.CompressFormat.JPEG, 90, baos)
val imageBase64 = Base64.encodeToString(baos.toByteArray(), Base64.NO_WRAP)

val request = TosUploadRequest(
    imageBase64 = imageBase64,
    format = "jpeg",
    prefix = "generated/"
)

// 使用 Retrofit 发送请求
tosApiService.uploadBase64("your-api-key", request)
    .enqueue(object : Callback<TosUploadResponse> {
        override fun onResponse(call: Call<TosUploadResponse>, response: Response<TosUploadResponse>) {
            val publicUrl = response.body()?.data?.publicUrl
        }
        override fun onFailure(call: Call<TosUploadResponse>, t: Throwable) {
            // 处理错误
        }
    })
```

---

## 性能基准

| 场景 | 预期耗时 |
|------|----------|
| 单图上传 (1MB) | ~500-800ms |
| 批量 10 图 (各 1MB) | ~1-1.5s (并发) |
| 健康检查 (缓存命中) | <5ms |
| 健康检查 (缓存未命中) | ~100-200ms |

---

## 常见问题

### Q: 为什么上传失败提示 "Invalid file format"？

**A**: 可能原因：

1. 文件不是有效的 JPEG/PNG/WEBP 格式
2. Base64 字符串包含了 `data:image/jpeg;base64,` 前缀（服务会自动处理，但建议不要包含）
3. 文件已损坏

### Q: 上传大文件时超时怎么办？

**A**:

1. 确保文件不超过 10MB 限制
2. 检查网络连接质量
3. 对于大图，建议客户端先压缩再上传

### Q: TOS 连接状态显示 error？

**A**: 可能原因：

1. TOS AK/SK 配置错误
2. TOS Bucket 不存在或无访问权限
3. 网络问题导致无法访问 TOS 服务
