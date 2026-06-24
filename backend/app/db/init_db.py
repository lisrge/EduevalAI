import random

from sqlalchemy import inspect, text
from sqlalchemy.orm import selectinload

from app.db.base import Base, SessionLocal, engine
from app.models.application import ApplicationRecord, ScoreResult
from app.models.blog import BlogAuditItem, BlogCrawlRun, BlogPost, BlogSource
from app.models.code_analysis import SubmissionCodeAnalysis
from app.models.course import Assignment, Course
from app.models.document_draft import ApplicationDraft, TaskDraft
from app.models.document_import import DocumentImportBatch, DocumentImportFile
from app.models.gitee_profile import UserGiteeProfile
from app.models.group import UserGroup
from app.models.homework_file import HomeworkFile
from app.models.request import UserChangeRequest
from app.models.repository import RepoBinding, RepoCommitSnapshot
from app.models.submission import AssignmentSubmission, SubmissionAsset, SubmissionMember
from app.models.teacher_review_assignment import TeacherReviewAssignment
from app.models.teacher_score import TeacherScoreRecord
from app.models.user import User, UserSession


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        inspector = inspect(conn)
        try:
            group_cols = {c["name"] for c in inspector.get_columns("user_groups")}
        except Exception:
            group_cols = set()

        if group_cols and "group_number" not in group_cols:
            conn.exec_driver_sql("ALTER TABLE user_groups ADD COLUMN group_number INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE UNIQUE INDEX ux_user_groups_group_number ON user_groups(group_number)")
            except Exception:
                pass
            try:
                conn.exec_driver_sql("UPDATE user_groups SET group_number = id WHERE group_number IS NULL")
            except Exception:
                pass
            try:
                conn.exec_driver_sql("ALTER TABLE user_groups MODIFY COLUMN group_number INTEGER NOT NULL")
            except Exception:
                pass

        if group_cols and "leader_user_id" not in group_cols:
            conn.exec_driver_sql("ALTER TABLE user_groups ADD COLUMN leader_user_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_user_groups_leader_user_id ON user_groups(leader_user_id)")
            except Exception:
                pass
        if group_cols and "repo_url" not in group_cols:
            conn.exec_driver_sql("ALTER TABLE user_groups ADD COLUMN repo_url VARCHAR(800) NULL")
        if group_cols and "import_key" not in group_cols:
            conn.exec_driver_sql("ALTER TABLE user_groups ADD COLUMN import_key VARCHAR(128) NULL")
            try:
                conn.exec_driver_sql("CREATE UNIQUE INDEX ux_user_groups_import_key ON user_groups(import_key)")
            except Exception:
                pass
        if group_cols:
            try:
                rows = conn.exec_driver_sql("SELECT id, group_number FROM user_groups WHERE group_number IS NOT NULL").fetchall()
                for row in rows:
                    group_id = row[0]
                    group_number = int(row[1])
                    conn.execute(
                        text("UPDATE user_groups SET name=:name, code=:code WHERE id=:id"),
                        {
                            "id": group_id,
                            "name": f"\u7b2c{group_number}\u7ec4",
                            "code": f"G{group_number:03d}",
                        },
                    )
            except Exception:
                pass

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

        if user_cols and "real_name" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN real_name VARCHAR(100) NOT NULL DEFAULT ''")

        if user_cols and "is_root_admin" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN is_root_admin TINYINT(1) NOT NULL DEFAULT 0")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_users_is_root_admin ON users(is_root_admin)")
            except Exception:
                pass

        if user_cols and "group_id" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN group_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_users_group_id ON users(group_id)")
            except Exception:
                pass

        if user_cols and "blog_home_url" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN blog_home_url VARCHAR(800) NULL")

        if user_cols and "blog_enabled" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN blog_enabled TINYINT(1) NOT NULL DEFAULT 1")

        if user_cols and "blog_crawl_status" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN blog_crawl_status VARCHAR(30) NOT NULL DEFAULT 'idle'")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_users_blog_crawl_status ON users(blog_crawl_status)")
            except Exception:
                pass

        if user_cols and "blog_last_crawled_at" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN blog_last_crawled_at DATETIME NULL")

        if user_cols and "application_reupload_allowed" not in user_cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN application_reupload_allowed TINYINT(1) NOT NULL DEFAULT 0")

        if user_cols:
            conn.exec_driver_sql("UPDATE users SET role='user' WHERE role IS NULL OR role=''")
            try:
                conn.exec_driver_sql("UPDATE users SET real_name='' WHERE real_name IS NULL")
            except Exception:
                pass
            try:
                conn.exec_driver_sql("UPDATE users SET is_root_admin=0 WHERE is_root_admin IS NULL")
            except Exception:
                pass
            try:
                conn.exec_driver_sql("UPDATE users SET blog_enabled=1 WHERE blog_enabled IS NULL")
            except Exception:
                pass
            try:
                conn.exec_driver_sql("UPDATE users SET blog_crawl_status='idle' WHERE blog_crawl_status IS NULL OR blog_crawl_status=''")
            except Exception:
                pass
            try:
                conn.exec_driver_sql("UPDATE users SET application_reupload_allowed=0 WHERE application_reupload_allowed IS NULL")
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
                conn.exec_driver_sql(
                    """
                    UPDATE users u
                    JOIN (
                      SELECT ar.uploader_user_id AS user_id, ar.student_name
                      FROM application_records ar
                      JOIN (
                        SELECT uploader_user_id, MAX(id) AS max_id
                        FROM application_records
                        WHERE uploader_user_id IS NOT NULL
                        GROUP BY uploader_user_id
                      ) latest
                        ON latest.uploader_user_id = ar.uploader_user_id
                       AND latest.max_id = ar.id
                    ) x ON x.user_id = u.id
                    SET u.real_name = x.student_name
                    WHERE (u.real_name IS NULL OR u.real_name = '')
                      AND x.student_name IS NOT NULL
                      AND x.student_name <> ''
                    """
                )
            except Exception:
                pass

        try:
            blog_cols = {c["name"] for c in inspector.get_columns("blog_posts")}
        except Exception:
            blog_cols = set()

        if blog_cols and "source" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN source VARCHAR(50) NOT NULL DEFAULT 'csdn'")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_source ON blog_posts(source)")
            except Exception:
                pass
        if blog_cols and "source_id" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN source_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_source_id ON blog_posts(source_id)")
            except Exception:
                pass
        if blog_cols and "article_uid" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN article_uid VARCHAR(128) NOT NULL DEFAULT ''")
        if blog_cols and "category" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN category VARCHAR(30) NOT NULL DEFAULT 'unknown'")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_category ON blog_posts(category)")
            except Exception:
                pass
        if blog_cols and "summary" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN summary TEXT NULL")
        if blog_cols and "summary_text" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN summary_text TEXT NULL")
            try:
                conn.exec_driver_sql("UPDATE blog_posts SET summary_text='' WHERE summary_text IS NULL")
            except Exception:
                pass
        if blog_cols and "content_text" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN content_text LONGTEXT NULL")
        if blog_cols and "work_items_json" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN work_items_json TEXT NULL")
            try:
                conn.exec_driver_sql("UPDATE blog_posts SET work_items_json='[]' WHERE work_items_json IS NULL")
            except Exception:
                pass
        if blog_cols and "snapshot_hash" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN snapshot_hash VARCHAR(64)")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_snapshot_hash ON blog_posts(snapshot_hash)")
            except Exception:
                pass
        if blog_cols and "raw_html_path" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN raw_html_path VARCHAR(1000) NOT NULL DEFAULT ''")
        if blog_cols and "screenshot_path" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN screenshot_path VARCHAR(1000) NOT NULL DEFAULT ''")
        if blog_cols and "published_at" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN published_at DATETIME NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_published_at ON blog_posts(published_at)")
            except Exception:
                pass
        if blog_cols and "word_count" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN word_count INTEGER NOT NULL DEFAULT 0")
        if blog_cols and "code_block_count" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN code_block_count INTEGER NOT NULL DEFAULT 0")
        if blog_cols and "number_count" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN number_count INTEGER NOT NULL DEFAULT 0")
        if blog_cols and "is_mostly_code" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN is_mostly_code TINYINT(1) NOT NULL DEFAULT 0")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_is_mostly_code ON blog_posts(is_mostly_code)")
            except Exception:
                pass
        if blog_cols and "is_popular_science" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN is_popular_science TINYINT(1) NOT NULL DEFAULT 0")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_is_popular_science ON blog_posts(is_popular_science)")
            except Exception:
                pass
        if blog_cols and "capture_status" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN capture_status VARCHAR(30) NOT NULL DEFAULT 'pending'")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_capture_status ON blog_posts(capture_status)")
            except Exception:
                pass
        if blog_cols and "capture_error" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN capture_error TEXT NULL")
        if blog_cols and "capture_timestamp" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN capture_timestamp DATETIME NULL")
        if blog_cols and "review_status" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN review_status VARCHAR(30) NOT NULL DEFAULT 'pending'")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_review_status ON blog_posts(review_status)")
            except Exception:
                pass
        if blog_cols and "review_note" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN review_note TEXT NULL")
        if blog_cols and "reviewed_at" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN reviewed_at DATETIME NULL")
        if blog_cols and "reviewed_by_admin_id" not in blog_cols:
            conn.exec_driver_sql("ALTER TABLE blog_posts ADD COLUMN reviewed_by_admin_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_blog_posts_reviewed_by_admin_id ON blog_posts(reviewed_by_admin_id)")
            except Exception:
                pass

        try:
            existing_indexes = {idx["name"] for idx in inspector.get_indexes("blog_posts")}
        except Exception:
            existing_indexes = set()
        if "ux_blog_posts_user_url" not in existing_indexes:
            try:
                conn.exec_driver_sql("CREATE UNIQUE INDEX ux_blog_posts_user_url ON blog_posts(user_id, url)")
            except Exception:
                pass

        # Existing MySQL installations may have created these as TEXT. Chinese
        # content reaches the 64 KiB byte limit long before a long article ends.
        if engine.dialect.name == "mysql" and blog_cols:
            for column_name in ("content_md", "content_text"):
                if column_name in blog_cols:
                    try:
                        # 先把 NULL 值设为空字符串
                        conn.exec_driver_sql(
                            f"UPDATE blog_posts SET {column_name} = '' WHERE {column_name} IS NULL"
                        )
                    except Exception:
                        pass
                    try:
                        # 再修改列类型
                        conn.exec_driver_sql(
                            f"ALTER TABLE blog_posts MODIFY COLUMN {column_name} LONGTEXT NOT NULL DEFAULT ''"
                        )
                    except Exception:
                        pass

        try:
            import_file_cols = {c["name"] for c in inspector.get_columns("document_import_files")}
        except Exception:
            import_file_cols = set()
        if import_file_cols and "group_id" not in import_file_cols:
            conn.exec_driver_sql("ALTER TABLE document_import_files ADD COLUMN group_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_document_import_files_group_id ON document_import_files(group_id)")
            except Exception:
                pass

        try:
            draft_cols = {c["name"] for c in inspector.get_columns("application_drafts")}
        except Exception:
            draft_cols = set()
        if draft_cols and "group_id" not in draft_cols:
            conn.exec_driver_sql("ALTER TABLE application_drafts ADD COLUMN group_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_application_drafts_group_id ON application_drafts(group_id)")
            except Exception:
                pass

        try:
            task_draft_cols = {c["name"] for c in inspector.get_columns("task_drafts")}
        except Exception:
            task_draft_cols = set()
        if task_draft_cols and "group_id" not in task_draft_cols:
            conn.exec_driver_sql("ALTER TABLE task_drafts ADD COLUMN group_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_task_drafts_group_id ON task_drafts(group_id)")
            except Exception:
                pass

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

        if cols and "group_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE application_records ADD COLUMN group_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_application_records_group_id ON application_records(group_id)")
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

        try:
            submission_cols = {c["name"] for c in inspector.get_columns("assignment_submissions")}
        except Exception:
            submission_cols = set()

        if submission_cols and "teacher_review_ai_json" not in submission_cols:
            conn.exec_driver_sql("ALTER TABLE assignment_submissions ADD COLUMN teacher_review_ai_json TEXT NULL")
            try:
                conn.exec_driver_sql("UPDATE assignment_submissions SET teacher_review_ai_json='' WHERE teacher_review_ai_json IS NULL")
            except Exception:
                pass

        if submission_cols and "group_id" not in submission_cols:
            conn.exec_driver_sql("ALTER TABLE assignment_submissions ADD COLUMN group_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_assignment_submissions_group_id ON assignment_submissions(group_id)")
            except Exception:
                pass
            try:
                conn.exec_driver_sql(
                    "UPDATE assignment_submissions "
                    "SET group_id = (SELECT users.group_id FROM users WHERE users.id = assignment_submissions.submitter_user_id) "
                    "WHERE group_id IS NULL"
                )
            except Exception:
                pass

        try:
            req_cols = {c["name"] for c in inspector.get_columns("user_change_requests")}
        except Exception:
            req_cols = set()
        if req_cols and "group_id" not in req_cols:
            conn.exec_driver_sql("ALTER TABLE user_change_requests ADD COLUMN group_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_user_change_requests_group_id ON user_change_requests(group_id)")
            except Exception:
                pass
        if req_cols and "assignment_id" not in req_cols:
            conn.exec_driver_sql("ALTER TABLE user_change_requests ADD COLUMN assignment_id INTEGER NULL")
            try:
                conn.exec_driver_sql("CREATE INDEX ix_user_change_requests_assignment_id ON user_change_requests(assignment_id)")
            except Exception:
                pass

        try:
            submission_asset_cols = {c["name"] for c in inspector.get_columns("submission_assets")}
        except Exception:
            submission_asset_cols = set()
        if engine.dialect.name == "mysql" and submission_asset_cols and "file_size" in submission_asset_cols:
            try:
                conn.exec_driver_sql("ALTER TABLE submission_assets MODIFY COLUMN file_size BIGINT NOT NULL DEFAULT 0")
            except Exception:
                pass

        try:
            repo_binding_cols = {c["name"] for c in inspector.get_columns("repo_bindings")}
        except Exception:
            repo_binding_cols = set()

        if repo_binding_cols and "analysis_summary_json" not in repo_binding_cols:
            conn.exec_driver_sql("ALTER TABLE repo_bindings ADD COLUMN analysis_summary_json TEXT NULL")
        if repo_binding_cols and "analysis_generated_at" not in repo_binding_cols:
            conn.exec_driver_sql("ALTER TABLE repo_bindings ADD COLUMN analysis_generated_at DATETIME NULL")

        try:
            homework_indexes = {idx["name"] for idx in inspector.get_indexes("homework_files")}
        except Exception:
            homework_indexes = set()
        try:
            homework_cols = {c["name"] for c in inspector.get_columns("homework_files")}
        except Exception:
            homework_cols = set()
        if engine.dialect.name == "mysql" and homework_cols and "file_size" in homework_cols:
            try:
                conn.exec_driver_sql("ALTER TABLE homework_files MODIFY COLUMN file_size BIGINT NOT NULL DEFAULT 0")
            except Exception:
                pass
        if "ux_homework_files_md5" not in homework_indexes:
            try:
                conn.exec_driver_sql("CREATE UNIQUE INDEX ux_homework_files_md5 ON homework_files(md5)")
            except Exception:
                pass

        try:
            teacher_score_cols = {c["name"] for c in inspector.get_columns("teacher_score_records")}
        except Exception:
            teacher_score_cols = set()

        if teacher_score_cols and "project_display_score" not in teacher_score_cols:
            conn.exec_driver_sql("ALTER TABLE teacher_score_records ADD COLUMN project_display_score INTEGER NOT NULL DEFAULT 0")
            try:
                conn.exec_driver_sql("UPDATE teacher_score_records SET project_display_score = COALESCE(completeness_score, 0)")
            except Exception:
                pass
        if teacher_score_cols and "project_innovation_score" not in teacher_score_cols:
            conn.exec_driver_sql("ALTER TABLE teacher_score_records ADD COLUMN project_innovation_score INTEGER NOT NULL DEFAULT 0")
            try:
                conn.exec_driver_sql("UPDATE teacher_score_records SET project_innovation_score = COALESCE(innovation_score, 0)")
            except Exception:
                pass
        if teacher_score_cols and "key_highlight_score" not in teacher_score_cols:
            conn.exec_driver_sql("ALTER TABLE teacher_score_records ADD COLUMN key_highlight_score INTEGER NOT NULL DEFAULT 0")
            try:
                conn.exec_driver_sql("UPDATE teacher_score_records SET key_highlight_score = COALESCE(code_quality_score, 0)")
            except Exception:
                pass
        if teacher_score_cols and "group_total_score" not in teacher_score_cols:
            conn.exec_driver_sql("ALTER TABLE teacher_score_records ADD COLUMN group_total_score FLOAT NOT NULL DEFAULT 0")
            try:
                conn.exec_driver_sql(
                    "UPDATE teacher_score_records SET group_total_score = "
                    "(COALESCE(project_display_score, COALESCE(completeness_score, 0)) * 0.5) + "
                    "(COALESCE(project_innovation_score, COALESCE(innovation_score, 0)) * 0.3) + "
                    "(COALESCE(key_highlight_score, COALESCE(code_quality_score, 0)) * 0.2)"
                )
            except Exception:
                pass
        if teacher_score_cols and "member_scores_json" not in teacher_score_cols:
            conn.exec_driver_sql("ALTER TABLE teacher_score_records ADD COLUMN member_scores_json TEXT NULL")
            try:
                conn.exec_driver_sql("UPDATE teacher_score_records SET member_scores_json='[]' WHERE member_scores_json IS NULL")
            except Exception:
                pass

        if engine.dialect.name == "mysql" and teacher_score_cols:
            try:
                conn.exec_driver_sql("ALTER TABLE teacher_score_records MODIFY COLUMN total_score DOUBLE NOT NULL DEFAULT 0")
            except Exception:
                pass
            try:
                conn.exec_driver_sql("ALTER TABLE teacher_score_records MODIFY COLUMN group_total_score DOUBLE NOT NULL DEFAULT 0")
            except Exception:
                pass
            for legacy_col in [
                "innovation_score",
                "completeness_score",
                "code_quality_score",
                "demo_score",
                "contribution_score",
            ]:
                if legacy_col in teacher_score_cols:
                    try:
                        conn.exec_driver_sql(
                            f"ALTER TABLE teacher_score_records MODIFY COLUMN {legacy_col} INTEGER NOT NULL DEFAULT 0"
                        )
                    except Exception:
                        pass

    db = SessionLocal()
    try:
        existing = db.query(Assignment).filter(Assignment.title == "2026项目实训末期检查").first()
        if not existing:
            creator = (
                db.query(User)
                .filter(User.is_root_admin == 1)
                .order_by(User.id.asc())
                .first()
            ) or db.query(User).order_by(User.id.asc()).first()

            course = db.query(Course).filter(Course.name == "默认课程").first()
            if not course:
                course = Course(
                    name="默认课程",
                    term="2026",
                    description="系统自动创建",
                    status="active",
                    created_by_user_id=int(creator.id) if creator else None,
                )
                db.add(course)
                db.flush()

            assignment = Assignment(
                course_id=course.id,
                title="2026项目实训末期检查",
                description="可上传任意类型文件",
                week_index=99,
                submission_mode="group",
                required_asset_types="",
                status="published",
            )
            db.add(assignment)
            db.commit()

        group_two = db.query(UserGroup).filter(UserGroup.group_number == 2).first()
        if group_two:
            users = (
                db.query(User)
                .filter(User.group_id == group_two.id)
                .order_by(User.id.asc())
                .all()
            )
            if users:
                existing_profiles = {
                    item.user_id: item
                    for item in db.query(UserGiteeProfile)
                    .filter(UserGiteeProfile.user_id.in_([user.id for user in users]))
                    .all()
                }
                submission = (
                    db.query(AssignmentSubmission)
                    .options(
                        selectinload(AssignmentSubmission.members),
                        selectinload(AssignmentSubmission.repo_binding).selectinload(RepoBinding.commits),
                    )
                    .filter(AssignmentSubmission.group_name == group_two.name)
                    .order_by(AssignmentSubmission.updated_at.desc(), AssignmentSubmission.id.desc())
                    .first()
                )
                author_names: list[str] = []
                if submission and submission.repo_binding:
                    author_names = sorted(
                        {
                            str(commit.author_name or "").strip()
                            for commit in list(submission.repo_binding.commits or [])
                            if str(commit.author_name or "").strip()
                        }
                    )
                rng = random.Random(20260623)
                rng.shuffle(author_names)
                fallback_names = [f"group2_dev_{index + 1:02d}" for index in range(len(users))]
                member_map = {
                    str(member.student_id or "").strip(): member
                    for member in list(getattr(submission, "members", []) or [])
                }
                changed = False
                for index, user in enumerate(users):
                    nickname = author_names[index] if index < len(author_names) else fallback_names[index]
                    profile = existing_profiles.get(user.id)
                    if not profile:
                        profile = UserGiteeProfile(
                            user_id=user.id,
                            student_id=user.student_id,
                            gitee_login=nickname,
                            gitee_display_name=nickname,
                            gitee_profile_url=f"https://gitee.com/{nickname}",
                            notes="系统初始化时为第二组生成的测试映射",
                        )
                        db.add(profile)
                        changed = True
                    member = member_map.get(str(user.student_id or "").strip())
                    if member and not str(member.git_author_names or "").strip():
                        member.git_author_names = nickname
                        changed = True
                if changed:
                    db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
