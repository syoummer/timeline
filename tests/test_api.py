"""API 测试"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    """测试健康检查端点"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_api_info():
    """测试 API 信息端点"""
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "version" in data
    assert "endpoints" in data


def test_analyze_missing_file():
    """测试缺少音频文件的请求"""
    response = client.post(
        "/api/v1/analyze",
        data={
            "current_time": "2024-01-15T10:30:00+08:00"
        }
    )
    assert response.status_code == 422  # FastAPI 验证错误


def test_analyze_missing_params():
    """测试缺少必需参数的请求"""
    # 创建一个模拟文件
    files = {"audio": ("test.m4a", b"fake audio data", "audio/m4a")}
    response = client.post(
        "/api/v1/analyze",
        files=files
    )
    assert response.status_code == 422  # FastAPI 验证错误
