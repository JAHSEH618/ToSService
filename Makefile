.PHONY: help build up down restart logs status health clean test dev

# ============================================
#  TOS Upload Service — 常用运维命令
# ============================================

IMAGE_NAME  := tos-upload-service
SERVICE     := tos-upload-service
COMPOSE     := docker compose

help: ## 显示所有可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# ---------- 构建 ----------

build: ## 构建 Docker 镜像
	$(COMPOSE) build

build-no-cache: ## 无缓存重新构建镜像
	$(COMPOSE) build --no-cache

# ---------- 启停 ----------

up: ## 后台启动服务
	$(COMPOSE) up -d --build
	@echo "\n✅ 服务已启动  →  http://localhost:$${SERVICE_PORT:-10086}/docs"

down: ## 停止并移除容器
	$(COMPOSE) down

restart: ## 重启服务
	$(COMPOSE) restart

# ---------- 监控 ----------

logs: ## 查看实时日志 (Ctrl+C 退出)
	$(COMPOSE) logs -f --tail=200

status: ## 查看容器状态
	$(COMPOSE) ps

health: ## 执行健康检查
	@curl -sf http://localhost:$${SERVICE_PORT:-10086}/api/v1/health | python3 -m json.tool \
		|| echo "❌ 服务不可达"

# ---------- 开发 ----------

dev: ## 本地开发启动 (热重载)
	uvicorn app.main:app --reload --port 10086

test: ## 运行测试
	python -m pytest tests/ -v

# ---------- 清理 ----------

clean: ## 停止容器并清理镜像、日志
	$(COMPOSE) down --rmi local -v
	rm -rf logs/*.log
	@echo "🧹 清理完成"
