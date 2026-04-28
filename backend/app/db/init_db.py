from sqlalchemy import inspect, text

from app.db.base import Base, engine
from app.models.application import ApplicationRecord, ScoreResult
from app.models.blog import BlogPost
from app.models.document_draft import ApplicationDraft, TaskDraft
from app.models.user import User, UserSession


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        inspector = inspect(conn)
        try:
            user_cols = {c["name"] for c in inspector.get_columns("users")}
        except Exception:
            user_cols = set()

        if user_cols and "role" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_users_role ON users(role)")
            except Exception:
                pass

        if user_cols and "is_root_admin" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_root_admin TINYINT(1) NOT NULL DEFAULT 0")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_users_is_root_admin ON users(is_root_admin)")
            except Exception:
                pass

        if user_cols:
            conn.exec_driver_sql("UPDATE users SET role='user' WHERE role IS NULL OR role=''")
            try:
                conn.exec_driver_sql("UPDATE users SET is_root_admin=0 WHERE is_root_admin IS NULL")
            except Exception:
                pass

            res = conn.exec_driver_sql("SELECT COUNT(*) FROM users WHERE is_root_admin=1")
            root_count = (res.fetchone() or [0])[0]
            if root_count == 0:
                first = conn.exec_driver_sql("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
                if first:
                    conn.execute(
                        text("UPDATE users SET role='admin', is_root_admin=1 WHERE id=:id"),
                        {"id": first[0]},
                    )
            conn.exec_driver_sql("UPDATE users SET role='admin' WHERE is_root_admin=1")

        try:
            _ = inspector.get_columns("blog_posts")
        except Exception:
            pass

        root = conn.exec_driver_sql("SELECT id FROM users WHERE is_root_admin=1 LIMIT 1").fetchone()
        if root:
            uid = root[0]
            existing_blog = conn.execute(text("SELECT COUNT(*) FROM blog_posts WHERE user_id=:uid"), {"uid": uid}).fetchone()
            count = (existing_blog or [0])[0]
            if count == 0:
                sample = (
                    "# 示例博客：Markdown 预览测试\n\n"
                    "这是一篇用于测试“内嵌式预览（md）”的示例博客。\n\n"
                    "## 内容要点\n\n"
                    "- 这是一个列表项\n"
                    "- 支持 `inline code`\n\n"
                    "## 代码块\n\n"
                    "```python\n"
                    "def hello():\n"
                    "    return \"Hello, EduEvalAI\"\n"
                    "```\n\n"
                    "## 结论\n\n"
                    "后续由爬虫接口写入真实博客内容与正常/不正常判定结果。\n"
                )
                conn.execute(
                    text(
                        "INSERT INTO blog_posts (user_id, title, url, status, content_md, created_at, updated_at) "
                        "VALUES (:user_id, :title, :url, :status, :content_md, UTC_TIMESTAMP(), UTC_TIMESTAMP())"
                    ),
                    {
                        "user_id": uid,
                        "title": "示例博客（Markdown 预览）",
                        "url": "",
                        "status": "normal",
                        "content_md": sample,
                    },
                )

        try:
            cols = {c["name"] for c in inspector.get_columns("application_records")}
        except Exception:
            cols = set()

        if cols and "uploader_user_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE application_records ADD COLUMN uploader_user_id INTEGER")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_application_records_uploader_user_id ON application_records(uploader_user_id)")
            except Exception:
                pass

        if cols and "file_hash" not in cols:
            conn.exec_driver_sql("ALTER TABLE application_records ADD COLUMN file_hash VARCHAR(64)")

        index_name = "ux_application_records_file_hash"
        try:
            existing_indexes = {idx["name"] for idx in inspector.get_indexes("application_records")}
        except Exception:
            existing_indexes = set()

        if index_name not in existing_indexes:
            try:
                conn.exec_driver_sql(f"CREATE UNIQUE INDEX {index_name} ON application_records(file_hash)")
            except Exception:
                pass


if __name__ == "__main__":
    init_db()
