import unittest
from datetime import datetime, timedelta

from app.services.blog_crawler_service import (
    _extract_post_links,
    _is_pagination_url,
    _project_relevance,
    build_blog_user_risk,
)


class ProjectBlogFilterTests(unittest.TestCase):
    def test_engineering_work_is_kept_without_training_phrase(self):
        text = "本周完成智能体记忆模块，实现知识库检索接口，并修复多轮对话状态丢失问题。"
        is_project, score, reasons = _project_relevance(text, "智能体记忆功能开发")
        self.assertTrue(is_project)
        self.assertGreater(score, 0)
        self.assertTrue(any(item.startswith("engineering:") for item in reasons))

    def test_generic_tutorial_is_filtered(self):
        text = "本文介绍什么是智能体，并讲解大语言模型的基本概念和常见使用方法。"
        is_project, _, _ = _project_relevance(text, "智能体入门教程")
        self.assertFalse(is_project)

    def test_known_project_name_matches_article(self):
        text = "EduEvalAI 完成了博客抓取模块的接口联调。"
        is_project, _, reasons = _project_relevance(text, "抓取模块进度", "EduEvalAI 教学评测系统")
        self.assertTrue(is_project)
        self.assertTrue(any(item.startswith("project-match:") for item in reasons))

    def test_generic_link_collection_is_not_capped_at_twenty(self):
        html = "".join(f'<a href="/posts/{index}">post</a>' for index in range(80))
        links = _extract_post_links("https://example.com/blog", html)
        self.assertEqual(len(links), 80)

    def test_pagination_urls_are_detected(self):
        self.assertTrue(_is_pagination_url("https://example.com/blog/page/12"))
        self.assertTrue(_is_pagination_url("https://example.com/blog?page=3"))
        self.assertFalse(_is_pagination_url("https://example.com/posts/12"))

    def test_eight_posts_in_one_week_are_flagged(self):
        start = datetime(2026, 6, 1)
        dates = [start + timedelta(hours=index * 12) for index in range(8)]
        span, flags = build_blog_user_risk(8, dates, False, False, "success", True)
        self.assertLessEqual(span, 7)
        self.assertIn("eight_posts_within_1_week", flags)

    def test_incomplete_failed_user_is_retryable(self):
        _, flags = build_blog_user_risk(5, [], True, True, "failed", True)
        self.assertIn("blog_count_below_8", flags)
        self.assertIn("code_only_blog_present", flags)
        self.assertIn("empty_popular_science_present", flags)
        self.assertIn("crawl_failed_retry_required", flags)


if __name__ == "__main__":
    unittest.main()
