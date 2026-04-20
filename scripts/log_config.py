"""
ADDS 统一日志配置模块

用法：
  # 在应用入口（adds.py）调用一次：
  from log_config import configure_logging
  configure_logging(debug=True, ai_dir=ai_dir)

  # 在各模块中正常使用：
  import logging
  logger = logging.getLogger(__name__)

设计原则：
  - 默认模式：日志完全静默（NullHandler），stdout/stderr 无任何日志输出
  - Debug 模式：日志只写文件（.ai/logs/adds-YYYYMMDD_HHMMSS.log），不影响交互界面
  - 每次启动生成独立日志文件，按时间戳命名，避免累积覆盖
  - 所有模块通过 logging.getLogger(__name__) 获取 logger，只负责产生日志
  - 不允许任何模块调用 logging.basicConfig()，统一由此模块管理
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# 日志目录名（相对于 ai_dir）
_LOG_DIR_NAME = "logs"

# 日志文件名前缀
_LOG_FILE_PREFIX = "adds-"

# 日志格式
_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 标记是否已初始化（避免重复配置）
_initialized = False


def _generate_log_filename() -> str:
    """生成基于时间戳的日志文件名，格式：adds-YYYYMMDD_HHMMSS.log"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{_LOG_FILE_PREFIX}{ts}.log"


def configure_logging(
    debug: bool = False,
    ai_dir: Optional[Path] = None,
    log_file: Optional[str] = None,
) -> None:
    """
    统一配置 ADDS 日志系统。

    此函数应在应用启动时调用一次，通常在 adds.py 的 start() 方法中。

    参数：
        debug:    是否启用 debug 模式。True → 日志写文件；False → 完全静默
        ai_dir:   项目 .ai 目录路径，日志写入 ai_dir/logs/
        log_file: 自定义日志文件名（不含路径），默认按时间戳生成
    """
    global _initialized

    root_logger = logging.getLogger()
    # 清除所有已有 handler（包括其他库或 basicConfig 留下的）
    root_logger.handlers.clear()

    if debug:
        # 日志目录：.ai/logs/
        if ai_dir is None:
            ai_dir = Path(".ai")
        log_dir = Path(ai_dir) / _LOG_DIR_NAME
        log_dir.mkdir(parents=True, exist_ok=True)

        filename = log_file or _generate_log_filename()
        log_path = log_dir / filename

        # 文件 handler：写文件，不影响终端
        file_handler = logging.FileHandler(
            str(log_path), mode="a", encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
        )
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.DEBUG)

        logger = logging.getLogger(__name__)
        logger.info("Debug logging enabled → %s", log_path)
    else:
        # 默认模式：NullHandler，不输出到 stdout/stderr
        root_logger.addHandler(logging.NullHandler())
        root_logger.setLevel(logging.CRITICAL + 1)

    _initialized = True


def is_configured() -> bool:
    """日志系统是否已初始化"""
    return _initialized


def configure_standalone_logging(level: int = logging.DEBUG) -> None:
    """
    为独立运行的模块（python xxx.py）配置简单日志。

    仅用于 if __name__ == "__main__" 的开发调试场景。
    不影响 ADDS 主应用的日志配置。

    参数：
        level: 日志级别，默认 DEBUG
    """
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(
        logging.Formatter("%(levelname)s: %(message)s")
    )
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
