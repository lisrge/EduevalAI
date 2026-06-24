"""
简单的MySQL连接测试
"""
import pymysql

def test_mysql_connection():
    print("🔍 测试MySQL连接...")
    print()
    
    # 你的数据库配置
    config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '823525',
        'charset': 'utf8mb4'
    }
    
    try:
        # 尝试连接（不指定数据库）
        conn = pymysql.connect(**config)
        print("✅ 成功连接到MySQL！")
        print()
        
        cursor = conn.cursor()
        
        # 查看所有数据库
        cursor.execute("SHOW DATABASES")
        databases = cursor.fetchall()
        print("📚 所有数据库:")
        for db in databases:
            print(f"   - {db[0]}")
        
        # 检查是否有 edueval_ai
        has_edueval = any('edueval_ai' in db for db in databases)
        print()
        
        if has_edueval:
            print("✅ 数据库 'edueval_ai' 存在！")
            cursor.execute("USE edueval_ai")
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            print()
            print(f"📊 数据库中的表 ({len(tables)} 个):")
            for table in tables:
                print(f"   - {table[0]}")
        else:
            print("⚠️  数据库 'edueval_ai' 不存在！")
            print()
            print("💡 你可以创建它:")
            print("   CREATE DATABASE edueval_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        print("💡 请检查:")
        print("  1. MySQL服务是否运行")
        print("  2. 用户名和密码是否正确")
        print("  3. 端口3306是否被占用")

if __name__ == "__main__":
    test_mysql_connection()
