"""命令行导入工具。

用法：
  python import_cli.py <文件或目录> [更多文件/目录 ...]
  python import_cli.py seed            # 生成示例数据
  python import_cli.py count           # 查看库内活动数
"""
from __future__ import annotations

import sys

from core import db, seed
from ingest import loader


def main() -> None:
    args = sys.argv[1:]
    db.init_db()

    if not args or args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return

    if args[0] == "seed":
        wrote = seed.run(force=False)
        print("生成示例数据" if wrote else "库中已有数据，未重复生成")
        print(f"库内活动数：{db.activity_count()}")
        return

    if args[0] == "count":
        print(f"库内活动数：{db.activity_count()}")
        return

    for a in args:
        for r in loader.import_path(a):
            print(f"[{r['status']:7}] {r['filename']}: {r['message']}")
    print(f"完成。库内活动数：{db.activity_count()}")


if __name__ == "__main__":
    main()
