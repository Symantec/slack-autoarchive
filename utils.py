""" Helper functions that don't quite belong in the slack_autoarchive class """

import logging


def get_logger(logger_name, logger_file, log_level=logging.INFO):
    """ Setup the logger and return it. """
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    logging.basicConfig(level=log_level,
                        format=log_format,
                        datefmt='%y-%m-%d_%H:%M',
                        filename=logger_file,
                        filemode='w')
    # define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(log_level)
    # set a format which is simpler for console use
    formatter = logging.Formatter(log_format)
    # tell the handler to use this format
    console.setFormatter(formatter)
    # add the handler to the root logger
    logging.getLogger(logger_name).addHandler(console)

    return logging.getLogger(logger_name)
