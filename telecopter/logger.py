import sys
import logging


def setup_logger(name: str = __name__, level_str: str = "INFO") -> logging.Logger:
    log_level = getattr(logging, level_str.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger_instance = logging.getLogger(name)
    logger_instance.setLevel(log_level)
    if not logger_instance.handlers:
        logger_instance.addHandler(handler)
    else:
        for h_existing in logger_instance.handlers:
            h_existing.setLevel(log_level)
            h_existing.setFormatter(formatter)
    return logger_instance
