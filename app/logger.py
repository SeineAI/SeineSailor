import logging

def setup_logger(name, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    handler = logging.StreamHandler()
    handler.setLevel(level)

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger