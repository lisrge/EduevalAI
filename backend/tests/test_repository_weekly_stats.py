import unittest
from datetime import datetime

import app.db.init_db  # noqa: F401 - register all SQLAlchemy relationship targets
from app.models.repository import RepoBinding, RepoCommitSnapshot
from app.models.submission import AssignmentSubmission, SubmissionMember
from app.schemas.repository import RepoWeeklyStat
from app.services.repository_service import build_member_commit_histories, build_weekly_stats


class RepositoryWeeklyStatsTests(unittest.TestCase):
    def test_weekly_summary_contains_member_work_and_metrics(self):
        submission = AssignmentSubmission(id=1, assignment_id=1, submitter_user_id=1, student_id="1", student_name="A")
        submission.members = [
            SubmissionMember(
                id=10,
                student_name="张三",
                student_id="202600000001",
                contribution_source="git",
                git_author_names="zhangsan",
                git_author_emails="zhang@example.com",
            )
        ]
        binding = RepoBinding(id=2, submission_id=1, repo_owner="team", repo_name="agent", repo_url="https://gitee.com/team/agent")
        binding.submission = submission
        binding.commits = [
            RepoCommitSnapshot(
                commit_hash="a" * 40,
                author_name="zhangsan",
                author_email="zhang@example.com",
                message="feat: 实现智能体记忆模块",
                committed_at=datetime(2026, 6, 15, 10, 0),
                additions=120,
                deletions=8,
                changed_files=4,
            )
        ]

        rows = build_weekly_stats(binding)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["additions"], 120)
        self.assertIn("实现智能体记忆模块", rows[0]["work_summary"])
        self.assertEqual(rows[0]["members"][0]["student_name"], "张三")
        self.assertEqual(rows[0]["members"][0]["commit_count"], 1)
        self.assertEqual(RepoWeeklyStat(**rows[0]).members[0].student_name, "张三")

    def test_member_history_prefers_email_and_keeps_unmapped_commits(self):
        submission = AssignmentSubmission(id=2, assignment_id=1, submitter_user_id=1, student_id="1", student_name="A")
        submission.members = [
            SubmissionMember(
                id=20,
                student_name="张三",
                student_id="202600000001",
                contribution_source="git",
                git_author_names="zhangsan",
                git_author_emails="zhang@example.com",
            )
        ]
        binding = RepoBinding(id=3, submission_id=2, repo_owner="team", repo_name="agent", repo_url="https://gitee.com/team/agent")
        binding.submission = submission
        binding.commits = [
            RepoCommitSnapshot(commit_hash="b" * 40, author_name="renamed", author_email="zhang@example.com", message="fix", committed_at=datetime(2026, 6, 16), additions=5, deletions=2, changed_files=1),
            RepoCommitSnapshot(commit_hash="c" * 40, author_name="unknown", author_email="unknown@example.com", message="docs", committed_at=datetime(2026, 6, 17), additions=1, deletions=0, changed_files=1),
        ]
        result = build_member_commit_histories(binding)
        self.assertEqual(result["members"][0]["commit_count"], 1)
        self.assertEqual(result["members"][0]["additions"], 5)
        self.assertEqual(len(result["unmapped_commits"]), 1)


if __name__ == "__main__":
    unittest.main()
