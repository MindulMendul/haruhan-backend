import logging


def configure_logging() -> logging.Logger:
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger("haruhan")


logger = configure_logging()
