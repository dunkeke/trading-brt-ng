from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from .database import init_db, engine
from .config import settings
from .api import (
    trades_router, positions_router, history_router,
    market_router, reconciliation_router, export_router
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 创建应用
app = FastAPI(
    title="合约交易分析终端 API",
    description="交易持仓计算、盈亏分析、对账工具",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境需要限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(trades_router)
app.include_router(positions_router)
app.include_router(history_router)
app.include_router(market_router)
app.include_router(reconciliation_router)
app.include_router(export_router)

@app.on_event("startup")
async def startup_event():
    """应用启动时初始化"""
    logger.info("初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "合约交易分析终端 API",
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"全局异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"message": f"服务器内部错误: {str(exc)}"}
    )