# Streamlit 部署说明

## 本地启动

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Streamlit Cloud

1. 将仓库推送到 GitHub。
2. 在 Streamlit Cloud 选择该仓库。
3. Main file path 填写：`streamlit_app.py`。
4. Python 依赖使用仓库内 `requirements.txt`。

## 结构调整说明

- 新增 `streamlit_app.py`，将原有“解析交易 -> 重建持仓 -> 计算盈亏”的流程串为单体前端应用。
- 修复包初始化文件（新增 `__init__.py`），确保 `app.*` 模块可被 Streamlit 正常导入。
- 清理 `app/core/engine.py` 中错误依赖，避免运行时报 `ImportError`。

- 已新增 `runtime.txt`（Python 3.11），避免 Streamlit Cloud 默认 Python 3.13 与旧版依赖产生兼容问题。
