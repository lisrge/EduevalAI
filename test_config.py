"""
测试配置文件是否正确读取
"""
import sys
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings

def test_config():
    print("🔍 测试配置读取...")
    print()
    
    try:
        settings = get_settings()
        
        print("✅ 配置读取成功！")
        print()
        print("📋 配置信息:")
        print("=" * 60)
        print(f"  数据库URL: {settings.database_url}")
        print(f"  模型API Key: {settings.model_api_key[:10] if settings.model_api_key else 'None'}...")
        print(f"  CORS Origins: {settings.cors_origins}")
        print(f"  博客爬虫启用: {settings.blog_crawler_enabled}")
        print("=" * 60)
        print()
        print("🎉 配置测试通过！现在可以启动后端了！")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        print("💡 请确保 .env 文件在项目根目录")

if __name__ == "__main__":
    test_config()
