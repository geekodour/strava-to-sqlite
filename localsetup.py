import logging
import sys
from typing import Iterable

import snoop  # type: ignore
import structlog
from structlog.typing import Processor


def setup_snoop_dogg():
    """
    usage: @ss, @ss(depth=2), with ss:
    """
    snoop.install(snoop="ss")


# Current format is set based on the fact that we're using structlog,
# but otheriwse following works fine.
# FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
def setup_stdlogger():
    DATEFMT = "%d-%m-%Y %I:%M:%S %p"
    FORMAT = "%(message)s"
    logging.basicConfig(
        format=FORMAT,
        stream=sys.stdout,  # https://12factor.net/logs
        level=logging.INFO,
        datefmt=DATEFMT,
    )


# NOTE: we are using itertools.chain because processors is Iterable and does not
#       support + operator based on mypy errorlog
#       processors = processors + [structlog.dev.ConsoleRenderer()]
def get_structlog_processors() -> Iterable[Processor]:
    processors: Iterable[Processor] = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M.%S"),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
    ]
    if sys.stderr.isatty():
        return processors + [structlog.dev.ConsoleRenderer()]  # type: ignore
    else:
        return processors + [  # type: ignore
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]


# structlog logger
# see https://www.structlog.org/en/stable/contextvars.html
def setup_structlog():
    structlog.configure(
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
        wrapper_class=structlog.BoundLogger,
        processors=get_structlog_processors(),
    )


def init():
    # debug
    setup_snoop_dogg()
    # logging
    setup_stdlogger()
    setup_structlog()
