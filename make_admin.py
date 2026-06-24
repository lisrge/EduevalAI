import pymysql

config = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '823525',
    'database': 'edueval_ai',
    'charset': 'utf8mb4'
}

try:
    conn = pymysql.connect(**config)
    print("✅ 数据库连接成功！")
    print()
    
    cursor = conn.cursor()
    
    # 把 ID:3 的用户设为管理员
    cursor.execute("UPDATE users SET role='admin', is_root_admin=1 WHERE id = 3")
    conn.commit()
    print("✅ 已将 ID=3 的用户设为管理员！")
    print()
    
    # 再次查询确认
    cursor.execute("SELECT id, student_id, real_name, role, is_root_admin FROM users ORDER BY id ASC")
    users = cursor.fetchall()
    
    print("📊 更新后的用户列表：")
    print("="*80)
    for user in users:
        print(f"ID: {user[0]}, 学号: {user[1]}, 姓名: {user[2]}, 角色: {user[3]}, 超级管理员: {user[4]}")
    print("="*80)
    
except Exception as e:
    print(f"❌ 错误：{e}")
finally:
    if 'conn' in locals():
        conn.close()
