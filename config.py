"""全局配置：路径与默认值。"""
from pathlib import Path

# 项目根目录（app.py 所在）
BASE_DIR = Path(__file__).resolve().parent

# 数据目录与数据库
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "running.db"
UPLOAD_DIR = DATA_DIR / "uploads"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "Runalyze"
APP_SUBTITLE = "跑步数据分析"

# 用户默认参数（可被设置页覆盖）
DEFAULT_HR_MAX = 190
DEFAULT_UNITS = "metric"  # metric | imperial

# 支持的导入格式
SUPPORTED_EXTS = ("fit", "tcx", "gpx")
