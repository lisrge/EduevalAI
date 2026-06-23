"""Re-evaluate all blog posts with DeepSeek classification - concurrent version."""
import sys, os, time, json
from concurrent.futures import ThreadPoolExecutor, as_completed

os.chdir("D:/Code/eduevalAI/backend")
sys.path.insert(0, ".")

from app.db.base import SessionLocal
from app.models.blog import BlogPost
from app.models.user import User
from app.models.submission import AssignmentSubmission, SubmissionMember, SubmissionAsset
from app.models.course import Assignment, Course
from app.models.code_analysis import SubmissionCodeAnalysis
from app.models.repository import RepoBinding, RepoCommitSnapshot
from app.models.teacher_score import TeacherScoreRecord
from app.models.teacher_review_assignment import TeacherReviewAssignment
from app.models.group import UserGroup
from app.services.blog_crawler_service import analyze_project_blog, _project_context_for_user

MAX_WORKERS = 5  # concurrent DeepSeek calls

db = SessionLocal()
total = db.query(BlogPost).count()
print(f"Total posts: {total}")

# Pre-load project contexts for all users
project_contexts = {}
for row in db.query(BlogPost.user_id).distinct().all():
    user = db.query(User).filter(User.id == row[0]).first()
    if user:
        project_contexts[row[0]] = _project_context_for_user(db, user)
db.close()
print(f"Project contexts loaded for {len(project_contexts)} users")

def evaluate_post(post_id):
    db2 = SessionLocal()
    try:
        post = db2.query(BlogPost).filter(BlogPost.id == post_id).first()
        if not post:
            return None
        text = post.content_md or post.content_text or ""
        ctx = project_contexts.get(post.user_id, "")
        result = analyze_project_blog(text, post.title, ctx)

        # Use model's category directly
        model_cat = result.get("category", "project_update")
        if model_cat in ("code_dump", "project_code_dump"):
            cat = "project_code_dump"
        elif model_cat in ("popular_science", "project_science"):
            cat = "project_science"
        elif model_cat == "unrelated":
            cat = "unrelated"
        else:
            cat = "project_update"

        # Update in DB
        post.category = cat
        post.is_mostly_code = result["is_mostly_code"]
        post.is_popular_science = result["is_popular_science"]
        post.summary_text = (result.get("summary", "") or result.get("summary_text", ""))[:500]
        post.work_items_json = json.dumps(result.get("work_items", []), ensure_ascii=False)
        db2.commit()
        return {"id": post_id, "cat": cat, "ok": True}
    except Exception as e:
        db2.rollback()
        return {"id": post_id, "cat": "error", "ok": False, "err": str(e)[:100]}
    finally:
        db2.close()

# Get all post IDs
db = SessionLocal()
all_ids = [r[0] for r in db.query(BlogPost.id).order_by(BlogPost.id).all()]
db.close()

print(f"Processing {len(all_ids)} posts with {MAX_WORKERS} workers...")
updated = 0
errors = 0
cats = {}
t0 = time.time()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
    futures = {pool.submit(evaluate_post, pid): pid for pid in all_ids}
    for i, future in enumerate(as_completed(futures)):
        r = future.result()
        if r and r["ok"]:
            updated += 1
            cats[r["cat"]] = cats.get(r["cat"], 0) + 1
        else:
            errors += 1
        if (i + 1) % 100 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            remaining = (len(all_ids) - i - 1) / rate if rate > 0 else 0
            print(f"  {i+1}/{len(all_ids)}: {updated} updated, {errors} errors, {rate:.1f}/s, {remaining:.0f}s remaining")
            print(f"    categories: {cats}")

elapsed = time.time() - t0
print(f"Done in {elapsed:.0f}s: {updated} updated, {errors} errors")
print(f"Categories: {cats}")

