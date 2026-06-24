"""
简单的数据库检查脚本
用于查看数据库中的表
"""
import sys
from pathlib import Path

# 添加后端目录到路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.db.base import SessionLocal
from sqlalchemy import inspect

def check_database():
    print("🔍 正在检查数据库...")
    print()
    
    try:
        db = SessionLocal()
        
        # 获取所有表名
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()
        
        print(f"✅ 成功连接数据库！")
        print()
        print(f"📊 数据库中的表 ({len(tables)} 个):")
        print("=" * 50)
        
        for i, table in enumerate(tables, 1):
            print(f"{i:2d}. {table}")
        
        print("=" * 50)
        print()
        print("🎉 检查完成！")
        
        db.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        print("💡 请确保:")
        print("  1. MySQL服务正在运行")
        print("  2. 数据库 'edueval_ai' 已创建")
        print("  3. 用户名和密码正确")
        print("  4. .env 文件中的配置正确")

if __name__ == "__main__":
    check_database()
