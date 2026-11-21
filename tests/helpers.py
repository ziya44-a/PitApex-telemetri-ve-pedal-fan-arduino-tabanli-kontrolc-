import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.data_manager import DataManager  # noqa: E402


def temp_dm():
    d = tempfile.mkdtemp(prefix="pitapex_test_")
    return DataManager(root=os.path.join(d, "PitApex"))
