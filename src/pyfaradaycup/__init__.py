import logging

# Library code only creates loggers; applications such as the command
# line tools configure handlers. The NullHandler prevents Python's
# "last resort" handler from printing warnings to stderr when the
# application has not configured logging.
logging.getLogger(__name__).addHandler(logging.NullHandler())

from pyfaradaycup import decommutator
