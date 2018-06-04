import os
import pytest


@pytest.fixture
def xml_path():
    path = os.path.join(os.path.dirname(__file__), "data", "xml_data.xml")
    return path
