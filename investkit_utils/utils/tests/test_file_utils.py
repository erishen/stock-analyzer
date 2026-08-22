import os
import shutil
import tempfile
import time

from investkit_utils.utils.file_utils import (
    clean_dir,
    copy_file,
    ensure_dir,
    find_files,
    format_file_size,
    get_file_info,
    get_latest_file,
    move_file,
    read_json,
    read_lines,
    read_text,
    write_json,
    write_text,
)


class TestEnsureDir:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_creates_nested_dir(self):
        path = os.path.join(self.temp_dir, "a", "b", "c")
        result = ensure_dir(path)
        assert os.path.isdir(path)
        assert result.name == "c"

    def test_existing_dir(self):
        result = ensure_dir(self.temp_dir)
        assert os.path.isdir(self.temp_dir)


class TestReadWriteJson:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_read(self):
        path = os.path.join(self.temp_dir, "test.json")
        data = {"key": "value", "num": 42, "list": [1, 2, 3]}
        write_json(path, data)
        result = read_json(path)
        assert result == data

    def test_read_nonexistent(self):
        assert read_json("no_file.json", default={"a": 1}) == {"a": 1}

    def test_unicode(self):
        path = os.path.join(self.temp_dir, "cn.json")
        data = {"名称": "测试"}
        write_json(path, data)
        result = read_json(path)
        assert result["名称"] == "测试"


class TestReadWriteText:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_and_read(self):
        path = os.path.join(self.temp_dir, "test.txt")
        write_text(path, "Hello World")
        assert read_text(path) == "Hello World"

    def test_append(self):
        path = os.path.join(self.temp_dir, "test.txt")
        write_text(path, "Line1\n")
        write_text(path, "Line2\n", append=True)
        content = read_text(path)
        assert "Line1" in content
        assert "Line2" in content

    def test_read_nonexistent(self):
        assert read_text("no_file.txt") == ""


class TestReadLines:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic(self):
        path = os.path.join(self.temp_dir, "test.txt")
        write_text(path, "a\nb\nc\n")
        assert read_lines(path) == ["a", "b", "c"]

    def test_empty_lines_skipped(self):
        path = os.path.join(self.temp_dir, "test.txt")
        write_text(path, "a\n\nb\n")
        assert read_lines(path) == ["a", "b"]

    def test_nonexistent(self):
        assert read_lines("no_file.txt") == []


class TestGetFileInfo:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_basic(self):
        path = os.path.join(self.temp_dir, "test.txt")
        write_text(path, "Hello World")
        info = get_file_info(path)
        assert info["name"] == "test.txt"
        assert info["stem"] == "test"
        assert info["suffix"] == ".txt"
        assert info["is_file"] is True
        assert info["size"] == 11

    def test_nonexistent(self):
        assert get_file_info("no_file.txt") is None


class TestFormatFileSize:
    def test_bytes(self):
        assert format_file_size(512) == "512.00 B"

    def test_kb(self):
        assert format_file_size(1024) == "1.00 KB"

    def test_mb(self):
        assert format_file_size(1048576) == "1.00 MB"

    def test_gb(self):
        assert format_file_size(1073741824) == "1.00 GB"

    def test_zero(self):
        assert format_file_size(0) == "0.00 B"


class TestCleanDir:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clean_files(self):
        for i in range(3):
            write_text(os.path.join(self.temp_dir, f"f{i}.txt"), "x")
        count = clean_dir(self.temp_dir, "*.txt")
        assert count == 3

    def test_nonexistent_dir(self):
        assert clean_dir("/nonexistent") == 0


class TestCopyFile:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_copy(self):
        src = os.path.join(self.temp_dir, "src.txt")
        dst = os.path.join(self.temp_dir, "dst.txt")
        write_text(src, "content")
        assert copy_file(src, dst) is True
        assert read_text(dst) == "content"

    def test_src_not_exists(self):
        assert copy_file("/nonexistent", "/dst") is False

    def test_no_overwrite(self):
        src = os.path.join(self.temp_dir, "src.txt")
        dst = os.path.join(self.temp_dir, "dst.txt")
        write_text(src, "new")
        write_text(dst, "old")
        assert copy_file(src, dst, overwrite=False) is False
        assert read_text(dst) == "old"

    def test_overwrite(self):
        src = os.path.join(self.temp_dir, "src.txt")
        dst = os.path.join(self.temp_dir, "dst.txt")
        write_text(src, "new")
        write_text(dst, "old")
        assert copy_file(src, dst, overwrite=True) is True
        assert read_text(dst) == "new"


class TestMoveFile:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_move(self):
        src = os.path.join(self.temp_dir, "src.txt")
        dst = os.path.join(self.temp_dir, "dst.txt")
        write_text(src, "content")
        assert move_file(src, dst) is True
        assert not os.path.exists(src)
        assert read_text(dst) == "content"

    def test_src_not_exists(self):
        assert move_file("/nonexistent", "/dst") is False


class TestFindFiles:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_by_pattern(self):
        write_text(os.path.join(self.temp_dir, "a.txt"), "")
        write_text(os.path.join(self.temp_dir, "b.csv"), "")
        files = find_files(self.temp_dir, "*.txt")
        assert len(files) == 1

    def test_nonexistent_dir(self):
        assert find_files("/nonexistent") == []


class TestGetLatestFile:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_latest(self):
        f1 = os.path.join(self.temp_dir, "a.txt")
        f2 = os.path.join(self.temp_dir, "b.txt")
        write_text(f1, "a")
        time.sleep(0.1)
        write_text(f2, "b")
        latest = get_latest_file(self.temp_dir, "*.txt")
        assert latest.name == "b.txt"

    def test_empty_dir(self):
        assert get_latest_file(self.temp_dir) is None
