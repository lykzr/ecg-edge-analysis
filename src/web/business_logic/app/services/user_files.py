"""按账号归档测量与分析文件；数据库保留权限和任务索引。"""
import re
from app.services.storage import connect
from app.core.config import settings


def directory(owner, root=None):
    with connect() as db:
        row = db.execute('SELECT username FROM users WHERE id=?', (owner,)).fetchone()
    if not row:
        raise LookupError('用户不存在')
    name = re.sub(r'[^\w-]', '_', row['username'])[:60] or 'user'
    # 固定ID防止改名、大小写及清洗后的同名碰撞；显示名仅用于识别。
    base = (root or settings.upload_dir.parent) / 'users'
    existing = next(base.glob('*--' + owner), None)
    path = existing or base / (name + '--' + owner)
    path.mkdir(parents=True, exist_ok=True)
    return path
