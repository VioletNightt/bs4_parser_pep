from pathlib import Path

BASE_DIR = Path(__file__).parent
DATETIME_FORMAT = '%Y-%m-%d_%H-%M-%S'

LOG_DIR = BASE_DIR / 'logs'
LOG_FILE = LOG_DIR / 'parser.log'

OUTPUT_PRETTY = 'pretty'
OUTPUT_FILE = 'file'
OUTPUT_CHOICES = (OUTPUT_PRETTY, OUTPUT_FILE)

MAIN_DOC_URL = 'https://docs.python.org/3/'
PEP_URL = 'https://peps.python.org/'

EXPECTED_STATUS = {
    'A': ('Active', 'Accepted'),
    'D': ('Deferred',),
    'F': ('Final',),
    'P': ('Provisional',),
    'R': ('Rejected',),
    'S': ('Superseded',),
    'W': ('Withdrawn',),
    '': ('Draft', 'Active'),
}
