"""FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

from app.api import routes


# 创建 FastAPI 应用
app = FastAPI(
    title="Timeline API",
    description="语音驱动的日程记录工具 API",
    version="1.0.0"
)

# 配置 CORS（允许跨域请求，方便测试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含 API 路由
app.include_router(routes.router)

# 挂载静态文件目录（用于测试页面）
static_dir = Path(__file__).parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    # 根路径重定向到测试页面
    @app.get("/", include_in_schema=False)
    async def root():
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/static/index.html")
