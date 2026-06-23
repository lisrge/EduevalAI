import json
import unittest

import app.db.init_db  # noqa: F401 - register all SQLAlchemy relationship targets
from app.models.document_import import DocumentImportFile
from app.services.document_import_service import _fallback_parse, merge_batch_groups
from app.services.file_service import _safe_name


class DocumentImportTests(unittest.TestCase):
    def test_windows_unsafe_upload_name_is_sanitized(self):
        self.assertEqual(_safe_name("申请?书*.docx", "file"), "申请_书_.docx")

    def test_application_extracts_members_blogs_and_gitee(self):
        text = """
申请书
项目名称 | 智能教学智能体
团队名称 | 星火组
项目负责人 | 张三
张三 | 202600000001 | 软件工程 | 负责人
李四 | 202600000002 | 软件工程 | 后端
项目资料地址
项目博客地址：https://gitee.com/team/agent
成员个人博客地址：
https://blog.csdn.net/zhangsan
https://blog.csdn.net/lisi
项目介绍
"""
        parsed = _fallback_parse(text, "智能教学智能体申请书.docx")
        self.assertEqual(parsed["project_name"], "智能教学智能体")
        self.assertEqual(parsed["gitee_url"], "https://gitee.com/team/agent")
        self.assertEqual(parsed["members"][0]["blog_url"], "https://blog.csdn.net/zhangsan")
        self.assertEqual(parsed["members"][1]["student_id"], "202600000002")

    def test_application_and_task_merge_into_one_group(self):
        application = {
            "document_type": "application",
            "project_name": "智能教学智能体",
            "team_name": "星火组",
            "leader_name": "张三",
            "leader_student_id": "202600000001",
            "members": [{"name": "张三", "student_id": "202600000001", "blog_url": "https://a.example", "role": "组长"}],
            "gitee_url": "https://gitee.com/team/agent",
            "group_key": "app-key",
        }
        task = {
            "document_type": "task",
            "project_name": "智能教学智能体",
            "team_name": "星火组",
            "leader_name": "张三",
            "leader_student_id": "",
            "members": [],
            "gitee_url": "",
            "group_key": "task-key",
        }
        rows = [
            DocumentImportFile(id=1, batch_id=1, document_type="application", file_name="a.docx", file_path="a", file_hash="a", parse_status="parsed", parse_error="", group_key="app-key", parsed_json=json.dumps(application, ensure_ascii=False)),
            DocumentImportFile(id=2, batch_id=1, document_type="task", file_name="t.docx", file_path="t", file_hash="t", parse_status="parsed", parse_error="", group_key="task-key", parsed_json=json.dumps(task, ensure_ascii=False)),
        ]
        groups = merge_batch_groups(rows)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["application_file_ids"], [1])
        self.assertEqual(groups[0]["task_file_ids"], [2])
        self.assertEqual(groups[0]["leader_student_id"], "202600000001")


if __name__ == "__main__":
    unittest.main()
