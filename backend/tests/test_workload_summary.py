import unittest
from unittest.mock import patch

import app.db.init_db  # noqa: F401 - register all SQLAlchemy relationship targets
from app.models.submission import AssignmentSubmission, SubmissionMember
from app.services.workload_service import build_submission_workload_summary


class WorkloadSummaryTests(unittest.TestCase):
    def test_personal_statement_becomes_concrete_work_items(self):
        submission = AssignmentSubmission(
            id=1,
            assignment_id=1,
            submitter_user_id=1,
            student_id="202600000001",
            student_name="张三",
            project_name="智能体平台",
        )
        submission.assets = []
        submission.members = [
            SubmissionMember(
                id=1,
                student_name="张三",
                student_id="202600000001",
                project_role="后端",
                workload_percent=60,
                contribution_source="non_git",
                personal_statement="完成智能体记忆接口。修复会话状态丢失问题。参与了讨论。",
            )
        ]

        with patch("app.services.workload_service._request_semantic_workload", return_value={}):
            summary = build_submission_workload_summary(submission)

        member = summary.members[0]
        self.assertIn("完成智能体记忆接口", member.work_items)
        self.assertIn("修复会话状态丢失问题", member.work_items)
        self.assertIn("完成智能体记忆接口", member.summary_text)
        self.assertEqual(member.analysis_confidence, "statement_based")


if __name__ == "__main__":
    unittest.main()
