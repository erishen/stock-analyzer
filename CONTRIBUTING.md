# 贡献指南

感谢你对 Stock Analyzer 的关注！欢迎参与项目贡献。

## 开发环境设置

### 前置要求

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装步骤

```bash
# 克隆仓库
git clone https://github.com/erishen/stock-analyzer.git
cd stock-analyzer

# 安装依赖
uv sync

# 安装开发依赖
uv sync --extra dev

# 安装 Web 依赖（可选）
uv sync --extra web
```

## 开发流程

### 1. 创建分支

```bash
git checkout -b feature/your-feature-name
```

### 2. 编写代码

- 遵循 PEP 8 代码规范
- 使用类型注解
- 添加文档字符串

### 3. 运行测试

```bash
# 运行所有测试
make test

# 或使用 uv
uv run pytest

# 带覆盖率报告
uv run pytest --cov=src --cov-report=html
```

### 4. 代码检查

```bash
# 运行 lint
make lint

# 或使用 uv
uv run ruff check .
uv run ruff format .
```

### 5. 提交代码

使用规范的提交信息：

| 前缀 | 说明 |
|------|------|
| `feat:` | 新功能 |
| `fix:` | 修复 bug |
| `docs:` | 文档更新 |
| `test:` | 测试相关 |
| `refactor:` | 代码重构 |
| `style:` | 代码格式 |
| `chore:` | 构建/工具 |

示例：
```bash
git commit -m "feat: 添加北向资金数据获取功能"
```

### 6. 推送并创建 PR

```bash
git push origin feature/your-feature-name
```

然后在 GitHub 上创建 Pull Request。

## 代码规范

### Python 代码风格

```python
from pathlib import Path
from typing import Optional


def calculate_signal(
    code: str,
    date: str,
    min_score: Optional[int] = None,
) -> dict:
    """计算股票信号.

    Args:
        code: 股票代码
        date: 日期
        min_score: 最低分数

    Returns:
        信号字典
    """
    pass
```

### 文档字符串

使用 Google 风格的文档字符串：

```python
def run_backtest(
    strategy: str,
    start_date: str,
    end_date: str,
) -> BacktestResult:
    """运行策略回测.

    Args:
        strategy: 策略名称
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    Returns:
        BacktestResult: 回测结果对象

    Raises:
        ValueError: 日期格式错误

    Example:
        >>> result = run_backtest("trend_following", "2023-01-01", "2023-12-31")
        >>> print(result.annual_return)
    """
    pass
```

## 项目结构

```
stock-analyzer/
├── src/
│   ├── data/           # 数据获取和处理
│   ├── etl/            # ETL 管道
│   ├── scanner/        # 信号扫描器
│   ├── scorer/         # 评分系统
│   ├── strategy/       # 交易策略
│   ├── utils/          # 工具函数
│   └── web/            # Web API
├── tests/              # 测试文件
├── frontend/           # React 前端
└── output/             # 输出目录
```

## 添加新策略

1. 在 `src/strategy/` 创建策略文件
2. 继承 `BaseStrategy` 类
3. 实现 `generate_signals()` 方法
4. 添加测试文件
5. 更新文档

示例：

```python
from src.strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    """我的自定义策略."""

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号."""
        signals = data.copy()
        signals["signal"] = 0
        return signals
```

## 添加新信号

1. 在 `src/scanner/signals.py` 添加信号检测函数
2. 更新 `SignalType` 枚举
3. 添加测试用例
4. 更新 README 信号列表

## 报告问题

如果你发现了 bug 或有功能建议：

1. 搜索现有 issues，避免重复
2. 创建新 issue，包含：
   - 问题描述
   - 复现步骤
   - 期望行为
   - 实际行为
   - 环境信息

## 许可证

贡献的代码将以 MIT 许可证发布。
