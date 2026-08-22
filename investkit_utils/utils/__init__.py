"""
InvestKit 共享工具函数

提供各项目通用的工具函数。

模块:
- datetime_utils: 日期时间工具
- retry: 重试装饰器
- validators: 数据验证器
- numeric: 数值计算工具
- string_utils: 字符串工具
- financial: 金融计算工具
- data_utils: 数据处理工具
- file_utils: 文件工具
"""

from investkit_utils.utils.data_utils import (
    batch_process,
    chunk_list,
    deep_merge,
    flatten_dict,
    group_by,
    safe_get,
    to_decimal,
    to_json_serializable,
    unflatten_dict,
    unique_list,
)
from investkit_utils.utils.datetime_utils import (
    format_date,
    get_trading_days,
    is_trading_day,
    parse_date,
)
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
from investkit_utils.utils.financial import (
    calculate_cagr,
    calculate_compound_interest,
    calculate_irr,
    calculate_max_drawdown,
    calculate_position_size,
    calculate_profit_factor,
    calculate_sharpe_ratio,
    calculate_win_rate,
)
from investkit_utils.utils.numeric import (
    percentage_change,
    round_to,
    safe_divide,
)
from investkit_utils.utils.retry import (
    retry,
    retry_async,
)
from investkit_utils.utils.string_utils import (
    mask_sensitive,
    truncate_string,
)
from investkit_utils.utils.validators import (
    validate_amount,
    validate_percentage,
    validate_stock_code,
)

__all__ = [
    "batch_process",
    "calculate_cagr",
    "calculate_compound_interest",
    "calculate_irr",
    "calculate_max_drawdown",
    "calculate_position_size",
    "calculate_profit_factor",
    "calculate_sharpe_ratio",
    "calculate_win_rate",
    "chunk_list",
    "clean_dir",
    "copy_file",
    "deep_merge",
    "ensure_dir",
    "find_files",
    "flatten_dict",
    "format_date",
    "format_file_size",
    "get_file_info",
    "get_latest_file",
    "get_trading_days",
    "group_by",
    "is_trading_day",
    "mask_sensitive",
    "move_file",
    "parse_date",
    "percentage_change",
    "read_json",
    "read_lines",
    "read_text",
    "retry",
    "retry_async",
    "round_to",
    "safe_divide",
    "safe_get",
    "to_decimal",
    "to_json_serializable",
    "truncate_string",
    "unflatten_dict",
    "unique_list",
    "validate_amount",
    "validate_percentage",
    "validate_stock_code",
    "write_json",
    "write_text",
]
