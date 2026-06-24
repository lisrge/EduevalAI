import subprocess
import sys

print("🔍 在新进程中测试配置读取...")
print()

result = subprocess.run(
    [sys.executable, "-c", '''
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "backend"))
from app.core.config import get_settings
settings = get_settings()
print("数据库URL:", settings.database_url)
'''],
    capture_output=True,
    text=True,
    cwd=str(Path(__file__).parent)
)

print(result.stdout)
if result.stderr:
    print("错误:", result.stderr)
