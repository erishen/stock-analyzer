# Third-Party Notices

本项目自身按 MIT 分发（见 [LICENSE](LICENSE)）。以下第三方依赖随运行/构建引入，
各自保留原有许可证；本文件只做清单与声明，不改变其许可条款。
若分发镜像或打包分发，请连同本文件与各依赖的 LICENSE 一并携带。

> 许可证取自各依赖安装元数据（`License-Expression` / `License` 字段），
> 以各项目仓库的最新声明为准。

## Python 运行时依赖

| 依赖 | 许可证 | 用途 |
|---|---|---|
| akshare | MIT | 行情/数据源接口 |
| lightgbm | MIT | 横截面排名模型 |
| scikit-learn | BSD-3-Clause | Isolation Forest / K-Means |
| arch | NCSA (University of Illinois) | GARCH(1,1) |
| pandas | BSD-3-Clause | 数据处理 |
| numpy | BSD-3-Clause（聚合多项：0BSD / MIT / Zlib / CC0-1.0） | 数值计算 |
| scipy | BSD-3-Clause | 科学计算 |
| matplotlib | PSF-based (matplotlib license) | 图表输出 |
| tqdm | **MPL-2.0 AND MIT** | 进度条 |
| certifi | **MPL-2.0** | CA 证书包 |
| requests | Apache-2.0 | HTTP 客户端 |
| curl-cffi | MIT | TLS 指纹请求 |
| fastapi | MIT | Web API |
| uvicorn | BSD-3-Clause | ASGI 服务器 |
| pydantic | MIT | 数据模型/校验 |
| sqlalchemy | MIT | ORM |
| openpyxl | MIT | Excel 读写 |
| beautifulsoup4 | MIT | HTML 解析 |
| lxml | BSD-3-Clause | XML/HTML 解析 |
| pyyaml | MIT | 配置解析 |
| rich / questionary | MIT | CLI 交互 |

## 前端 / 构建依赖

| 依赖 | 许可证 | 用途 |
|---|---|---|
| react / react-dom | MIT | UI 框架 |
| echarts | Apache-2.0 | 图表 |
| echarts-for-react | MIT | ECharts React 封装 |
| marked | MIT | Markdown 渲染 |
| vite / typescript | MIT / Apache-2.0 | 构建与类型 |
| tailwindcss | MIT | 样式 |

## 说明

- **MPL-2.0**（`tqdm`、`certifi`）是文件级弱 copyleft：仅修改这些库自身文件时需公开修改，
  与本项目的 MIT 代码不冲突
- 本项目**不随仓库分发任何行情数据**；数据版权归各行情源所有，仅供本地研究使用
