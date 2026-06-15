"""临时文件工具"""

import os
import shutil
import tempfile
from contextlib import contextmanager


@contextmanager
def temp_directory():
    """
    创建临时目录

    使用示例:
        with temp_directory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            with open(filepath, "w") as f:
                f.write("test")
    """
    tmpdir = tempfile.mkdtemp()
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


@contextmanager
def temp_file(content: str = "", suffix: str = ".txt"):
    """
    创建临时文件

    Args:
        content: 文件内容
        suffix: 文件后缀

    使用示例:
        with temp_file("test content", ".json") as filepath:
            with open(filepath) as f:
                data = f.read()
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
        f.write(content)
        filepath = f.name
    try:
        yield filepath
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
