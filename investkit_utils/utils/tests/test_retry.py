import asyncio
import contextlib

from investkit_utils.utils.retry import retry, retry_async


class TestRetry:
    def test_success_first_attempt(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.01)
        def func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = func()
        assert result == "ok"
        assert call_count == 1

    def test_success_after_retries(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        result = func()
        assert result == "ok"
        assert call_count == 3

    def test_all_attempts_exhausted(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fail")

        try:
            func()
        except ValueError as e:
            assert str(e) == "always fail"
        else:
            raise AssertionError("Should have raised ValueError")
        assert call_count == 3

    def test_on_retry_callback(self):
        retry_info = []

        def on_retry(exc, attempt):
            retry_info.append((str(exc), attempt))

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,), on_retry=on_retry)
        def func():
            if len(retry_info) < 2:
                raise ValueError(f"fail-{len(retry_info)}")
            return "ok"

        result = func()
        assert result == "ok"
        assert len(retry_info) == 2
        assert retry_info[0] == ("fail-0", 1)
        assert retry_info[1] == ("fail-1", 2)

    def test_only_specified_exceptions_retried(self):
        call_count = 0

        @retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def func():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        try:
            func()
        except TypeError:
            pass
        else:
            raise AssertionError("Should have raised TypeError")
        assert call_count == 1

    def test_backoff_delay(self):
        import time

        call_count = 0

        @retry(max_attempts=3, delay=0.05, backoff=2.0, exceptions=(ValueError,))
        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("fail")
            return "ok"

        start = time.monotonic()
        result = func()
        elapsed = time.monotonic() - start
        assert result == "ok"
        assert elapsed >= 0.05 + 0.1

    def test_preserves_function_name(self):
        @retry(max_attempts=3, delay=0.01)
        def my_function():
            return "ok"

        assert my_function.__name__ == "my_function"

    def test_single_attempt(self):
        call_count = 0

        @retry(max_attempts=1, delay=0.01, exceptions=(ValueError,))
        def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("fail")

        with contextlib.suppress(ValueError):
            func()
        assert call_count == 1


class TestRetryAsync:
    def test_async_success_first_attempt(self):
        call_count = 0

        @retry_async(max_attempts=3, delay=0.01)
        async def func():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = asyncio.run(func())
        assert result == "ok"
        assert call_count == 1

    def test_async_success_after_retries(self):
        call_count = 0

        @retry_async(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "ok"

        result = asyncio.run(func())
        assert result == "ok"
        assert call_count == 2

    def test_async_all_attempts_exhausted(self):
        call_count = 0

        @retry_async(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def func():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fail")

        try:
            asyncio.run(func())
        except ValueError as e:
            assert str(e) == "always fail"
        else:
            raise AssertionError("Should have raised ValueError")
        assert call_count == 3

    def test_async_only_specified_exceptions_retried(self):
        call_count = 0

        @retry_async(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def func():
            nonlocal call_count
            call_count += 1
            raise TypeError("wrong type")

        try:
            asyncio.run(func())
        except TypeError:
            pass
        else:
            raise AssertionError("Should have raised TypeError")
        assert call_count == 1

    def test_async_preserves_function_name(self):
        @retry_async(max_attempts=3, delay=0.01)
        async def my_async_func():
            return "ok"

        assert my_async_func.__name__ == "my_async_func"
