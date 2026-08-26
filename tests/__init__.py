import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


_REAL_PLATFORM_TEMP = Path(os.path.realpath(tempfile.gettempdir()))
_TEST_TEMP_ROOT = Path(
    tempfile.mkdtemp(prefix="yuanli-health-tests-", dir=_REAL_PLATFORM_TEMP)
)
tempfile.tempdir = str(_TEST_TEMP_ROOT)
atexit.register(shutil.rmtree, _TEST_TEMP_ROOT, ignore_errors=True)
