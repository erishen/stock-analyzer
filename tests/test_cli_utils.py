"""
Tests for CLI Utilities.
CLI 工具测试
"""



from utils.cli_utils import (
    ColorScheme,
    OutputConfig,
    create_progress_bar,
    format_number,
    format_percent,
    format_price,
    print_error,
    print_header,
    print_info,
    print_section,
    print_signal_table,
    print_success,
    print_warning,
    progress_iterate,
)


class TestColorScheme:
    """测试颜色方案"""

    def test_colorize_bullish(self):
        """测试看涨颜色"""
        text = ColorScheme.colorize("看涨", "bullish")
        assert text.plain == "看涨"

    def test_colorize_bearish(self):
        """测试看跌颜色"""
        text = ColorScheme.colorize("看跌", "bearish")
        assert text.plain == "看跌"

    def test_colorize_unknown(self):
        """测试未知颜色类型"""
        text = ColorScheme.colorize("测试", "unknown")
        assert text.plain == "测试"


class TestOutputConfig:
    """测试输出配置"""

    def test_default_values(self):
        """测试默认值"""
        config = OutputConfig()
        assert config.show_progress is True
        assert config.color_output is True
        assert config.verbose is False
        assert config.json_output is False

    def test_custom_values(self):
        """测试自定义值"""
        config = OutputConfig(
            show_progress=False,
            color_output=False,
            verbose=True,
            json_output=True,
        )
        assert config.show_progress is False
        assert config.color_output is False
        assert config.verbose is True
        assert config.json_output is True


class TestPrintFunctions:
    """测试打印函数"""

    def test_print_header(self, capsys):
        """测试打印标题"""
        print_header("测试标题", "副标题")
        captured = capsys.readouterr()
        assert "测试标题" in captured.out

    def test_print_section(self, capsys):
        """测试打印分节"""
        print_section("测试分节")
        captured = capsys.readouterr()
        assert "测试分节" in captured.out

    def test_print_success(self, capsys):
        """测试打印成功"""
        print_success("操作成功")
        captured = capsys.readouterr()
        assert "操作成功" in captured.out

    def test_print_error(self, capsys):
        """测试打印错误"""
        print_error("操作失败")
        captured = capsys.readouterr()
        assert "操作失败" in captured.out

    def test_print_warning(self, capsys):
        """测试打印警告"""
        print_warning("警告信息")
        captured = capsys.readouterr()
        assert "警告信息" in captured.out

    def test_print_info(self, capsys):
        """测试打印信息"""
        print_info("提示信息")
        captured = capsys.readouterr()
        assert "提示信息" in captured.out


class TestPrintSignalTable:
    """测试信号表格打印"""

    def test_print_signal_table_empty(self, capsys):
        """测试空信号表格"""
        print_signal_table([], "空表格")
        captured = capsys.readouterr()
        assert "空表格" in captured.out

    def test_print_signal_table_with_data(self, capsys):
        """测试有数据的信号表格"""
        signals = [
            {
                "code": "000001",
                "name": "平安银行",
                "signal_type": "MACD金叉",
                "strength": "强",
                "score": 85.5,
                "price": 10.50,
                "change_percent": 2.5,
            },
            {
                "code": "000002",
                "name": "万科A",
                "signal_type": "KDJ死叉",
                "strength": "弱",
                "score": 25.0,
                "price": 8.20,
                "change_percent": -1.5,
            },
        ]
        print_signal_table(signals, "信号列表")
        captured = capsys.readouterr()
        assert "000001" in captured.out
        assert "平安银行" in captured.out


class TestFormatFunctions:
    """测试格式化函数"""

    def test_format_number_small(self):
        """测试小数字格式化"""
        result = format_number(123.45)
        assert result == "123.45"

    def test_format_number_thousands(self):
        """测试千位数字格式化"""
        result = format_number(12345)
        assert result == "12.35K"

    def test_format_number_millions(self):
        """测试百万数字格式化"""
        result = format_number(1234567)
        assert result == "1.23M"

    def test_format_percent_positive(self):
        """测试正百分比格式化"""
        result = format_percent(0.0525)
        assert result == "+5.25%"

    def test_format_percent_negative(self):
        """测试负百分比格式化"""
        result = format_percent(-0.0325)
        assert result == "-3.25%"

    def test_format_price_high(self):
        """测试高价格式化"""
        result = format_price(123.456)
        assert result == "123.46"

    def test_format_price_medium(self):
        """测试中价格式化"""
        result = format_price(12.3456)
        assert result == "12.346"

    def test_format_price_low(self):
        """测试低价格式化"""
        result = format_price(1.23456)
        assert result == "1.2346"


class TestProgressBar:
    """测试进度条"""

    def test_create_progress_bar(self):
        """测试创建进度条"""
        progress = create_progress_bar("处理中")
        assert progress is not None

    def test_progress_iterate(self):
        """测试进度迭代"""
        items = [1, 2, 3, 4, 5]

        def process(x):
            return x * 2

        results = progress_iterate(items, process, "处理中")
        assert results == [2, 4, 6, 8, 10]

    def test_progress_iterate_with_exception(self):
        """测试带异常的进度迭代"""
        items = [1, 2, "error", 4, 5]

        def process(x):
            if isinstance(x, str):
                raise ValueError("Error")
            return x * 2

        results = progress_iterate(items, process, "处理中")
        assert results == [2, 4, 8, 10]


class TestInteractiveFunctions:
    """测试交互函数"""

    def test_interactive_select_without_questionary(self):
        """测试无 questionary 的交互选择"""
        from utils.cli_utils import interactive_select

        result = interactive_select(["A", "B", "C"])
        assert result is None or result in ["A", "B", "C"]

    def test_interactive_multiselect_without_questionary(self):
        """测试无 questionary 的多选"""
        from utils.cli_utils import interactive_multiselect

        result = interactive_multiselect(["A", "B", "C"])
        assert result is None or isinstance(result, list)

    def test_interactive_confirm_without_questionary(self):
        """测试无 questionary 的确认"""
        from utils.cli_utils import interactive_confirm

        result = interactive_confirm("确认吗?", default=True)
        assert result is True

    def test_interactive_text_without_questionary(self):
        """测试无 questionary 的文本输入"""
        from utils.cli_utils import interactive_text

        result = interactive_text("输入:", default="默认值")
        assert result == "默认值"
