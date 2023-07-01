import logging

def configure_logging():
    logging.config.fileConfig('logging.conf')
    logger = logging.getLogger()
    speed_logger = logging.getLogger('speed_logger')
    return logger, speed_logger