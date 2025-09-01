import json
import os
import sys
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

# Re-added: Add the 'src' directory to sys.path for module discovery
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from configkit.core import ConfigBase # This import should now work

# --- Test Config Definitions ---


class SimpleConfig(ConfigBase):
    field1: int
    field2: str


class NestedConfig(ConfigBase):
    name: str
    simple: SimpleConfig


class PathResolvingConfig(ConfigBase):
    name: str
    # This union is key for testing path resolution
    nested: SimpleConfig | str


class ComplexConfig(ConfigBase):
    name: str
    list_of_simple: list[SimpleConfig]
    dict_of_simple: dict[str, SimpleConfig]


# --- Pytest Fixtures ---


@pytest.fixture
def temp_dir(tmp_path):
    """A fixture to create a temporary directory for test artifacts."""
    return tmp_path


# --- Test Cases ---


def test_creation_and_immutability():
    """Tests that subclasses are frozen dataclasses."""
    conf = SimpleConfig(field1=1, field2="test")
    assert is_dataclass(conf)

    with pytest.raises(FrozenInstanceError):
        conf.field1 = 2


def test_uid_consistency():
    """Tests the UID generation logic."""
    conf1 = SimpleConfig(field1=1, field2="test")
    conf2 = SimpleConfig(field1=1, field2="test")
    conf3 = SimpleConfig(field1=2, field2="test")

    assert conf1.uid == conf2.uid
    assert conf1.uid != conf3.uid

    # Test that json sorting provides consistent UIDs
    conf_a = SimpleConfig(field1=1, field2="a")
    conf_b_dict = {"field2": "a", "field1": 1}

    str_a = json.dumps(conf_a._to_dict(), sort_keys=True)
    str_b = json.dumps(conf_b_dict, sort_keys=True)
    assert str_a == str_b


def test_save_and_load_simple(temp_dir):
    """Tests saving and loading a simple config."""
    conf = SimpleConfig(field1=10, field2="hello")
    config_path = temp_dir / "simple.json"

    conf.save(config_path)
    assert config_path.exists()

    loaded_conf = SimpleConfig.load(config_path)

    assert loaded_conf == conf
    assert loaded_conf.uid == conf.uid


def test_load_nested_dict(temp_dir):
    """Tests loading a config with a nested config provided as a dict."""
    nested_conf = NestedConfig(
        name="outer", simple=SimpleConfig(field1=1, field2="inner")
    )
    config_path = temp_dir / "nested.json"
    nested_conf.save(config_path)

    loaded_conf = NestedConfig.load(config_path)

    assert loaded_conf == nested_conf
    assert isinstance(loaded_conf.simple, SimpleConfig)
    assert loaded_conf.simple.field1 == 1


def test_load_nested_path(temp_dir):
    """Tests loading a config where a nested config is a path."""
    simple_conf = SimpleConfig(field1=42, field2="the answer")
    simple_path = temp_dir / "simple_for_path.json"
    simple_conf.save(simple_path)

    # Create the outer config JSON manually with a path
    path_resolving_dict = {"name": "path-resolver", "nested": str(simple_path)}
    path_resolving_path = temp_dir / "path_resolving.json"
    with open(path_resolving_path, "w") as f:
        json.dump(path_resolving_dict, f)

    loaded_conf = PathResolvingConfig.load(path_resolving_path)

    assert loaded_conf.name == "path-resolver"
    assert isinstance(loaded_conf.nested, SimpleConfig)
    assert loaded_conf.nested == simple_conf


def test_load_with_extra_fields(temp_dir):
    """Tests that loading from a JSON with extra fields doesn't crash."""
    data = {"field1": 1, "field2": "abc", "extra_field": "should be ignored"}
    config_path = temp_dir / "extra.json"
    with open(config_path, "w") as f:
        json.dump(data, f)

    loaded_conf = SimpleConfig.load(config_path)

    assert not hasattr(loaded_conf, "extra_field")
    assert loaded_conf.field1 == 1


# --- Tests for the fix ---


def test_load_list_of_configs(temp_dir):
    """Tests loading a config with a list of nested configs (path and dict)."""
    simple_conf1 = SimpleConfig(field1=1, field2="one")
    simple_path1 = temp_dir / "simple1.json"
    simple_conf1.save(simple_path1)

    simple_conf2_dict = {"field1": 2, "field2": "two"}

    complex_dict = {
        "name": "complex-list",
        "list_of_simple": [
            str(simple_path1),  # one from path
            simple_conf2_dict,  # one from dict
        ],
        "dict_of_simple": {},  # empty for this test
    }
    complex_path = temp_dir / "complex_list.json"
    with open(complex_path, "w") as f:
        json.dump(complex_dict, f)

    loaded_conf = ComplexConfig.load(complex_path)

    assert len(loaded_conf.list_of_simple) == 2
    assert isinstance(loaded_conf.list_of_simple[0], SimpleConfig)
    assert isinstance(loaded_conf.list_of_simple[1], SimpleConfig)
    assert loaded_conf.list_of_simple[0] == simple_conf1
    assert loaded_conf.list_of_simple[1].field1 == 2


def test_load_dict_of_configs(temp_dir):
    """Tests loading a config with a dict of nested configs (path and dict)."""
    simple_conf1 = SimpleConfig(field1=1, field2="one")
    simple_path1 = temp_dir / "simple1_dict.json"
    simple_conf1.save(simple_path1)

    simple_conf2_dict = {"field1": 2, "field2": "two"}

    complex_dict = {
        "name": "complex-dict",
        "list_of_simple": [],  # empty for this test
        "dict_of_simple": {"key1": str(simple_path1), "key2": simple_conf2_dict},
    }
    complex_path = temp_dir / "complex_dict.json"
    with open(complex_path, "w") as f:
        json.dump(complex_dict, f)

    loaded_conf = ComplexConfig.load(complex_path)

    assert len(loaded_conf.dict_of_simple) == 2
    assert isinstance(loaded_conf.dict_of_simple["key1"], SimpleConfig)
    assert isinstance(loaded_conf.dict_of_simple["key2"], SimpleConfig)
    assert loaded_conf.dict_of_simple["key1"] == simple_conf1
    assert loaded_conf.dict_of_simple["key2"].field2 == "two"
