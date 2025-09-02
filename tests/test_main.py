import json
import os
import sys
from dataclasses import FrozenInstanceError, is_dataclass

import pytest

# Re-added: Add the 'src' directory to sys.path for module discovery
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from configkit.core import ConfigBase  # This import should now work

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


def test_uid_consistency_with_key_order(temp_dir):
    """Tests that UID is consistent regardless of dictionary key order when loaded from file."""
    conf1 = SimpleConfig(field1=1, field2="test")

    # Manually create a JSON string with different key order
    json_str_different_order = '{"field2": "test", "field1": 1}'
    temp_path = temp_dir / "temp_conf_order.json"
    with open(temp_path, "w") as f:
        f.write(json_str_different_order)

    conf2 = SimpleConfig.load(temp_path)

    assert conf1.uid == conf2.uid
    assert conf1 == conf2


def test_nested_config_uid_consistency(temp_dir):
    """
    Tests that a nested config's UID is consistent whether loaded from path,
    from an inline dict, or created directly in memory.
    """
    # 1. Create a simple nested config directly in memory
    inner_conf_direct = SimpleConfig(field1=100, field2="inner_value")
    outer_conf_direct = NestedConfig(name="common_name", simple=inner_conf_direct)

    # 2. Create the inner config and save it to a file
    inner_path = temp_dir / "inner_conf.json"
    inner_conf_direct.save(inner_path)

    # 3. Create an outer config that refers to the inner config via path
    outer_dict_from_path = {"name": "common_name", "simple": str(inner_path)}
    outer_path_file = temp_dir / "outer_from_path.json"
    with open(outer_path_file, "w") as f:
        json.dump(outer_dict_from_path, f)
    outer_conf_from_path = NestedConfig.load(outer_path_file)

    # 4. Create an outer config that refers to the inner config via inline dict
    outer_dict_from_inline = {
        "name": "common_name",
        "simple": {
            "field1": 100,
            "field2": "inner_value",
        },  # Same content as inner_conf_direct
    }
    outer_inline_file = temp_dir / "outer_from_inline.json"
    with open(outer_inline_file, "w") as f:
        json.dump(outer_dict_from_inline, f)
    outer_conf_from_inline = NestedConfig.load(outer_inline_file)

    # Assertions for outer configs
    assert outer_conf_direct == outer_conf_from_path
    assert outer_conf_direct == outer_conf_from_inline
    assert outer_conf_direct.uid == outer_conf_from_path.uid
    assert outer_conf_direct.uid == outer_conf_from_inline.uid


# --- New Tests for JSON/YAML --- #

def test_save_load_yaml(temp_dir):
    """Tests saving and loading a simple config using explicit YAML methods."""
    conf = SimpleConfig(field1=10, field2="hello_yaml")
    config_path = temp_dir / "simple.yaml"

    conf.save_yaml(config_path)
    assert config_path.exists()

    loaded_conf = SimpleConfig.load_yaml(config_path)

    assert loaded_conf == conf
    assert loaded_conf.uid == conf.uid

def test_save_load_smart_json(temp_dir):
    """Tests saving and loading a simple config using smart methods with .json suffix."""
    conf = SimpleConfig(field1=20, field2="smart_json")
    config_path = temp_dir / "smart.json"

    conf.save(config_path)
    assert config_path.exists()

    loaded_conf = SimpleConfig.load(config_path)

    assert loaded_conf == conf
    assert loaded_conf.uid == conf.uid

def test_save_load_smart_yaml(temp_dir):
    """Tests saving and loading a simple config using smart methods with .yaml suffix."""
    conf = SimpleConfig(field1=30, field2="smart_yaml")
    config_path = temp_dir / "smart.yaml"

    conf.save(config_path)
    assert config_path.exists()

    loaded_conf = SimpleConfig.load(config_path)

    assert loaded_conf == conf
    assert loaded_conf.uid == conf.uid

def test_save_unsupported_extension(temp_dir):
    """Tests that saving with an unsupported extension raises a ValueError."""
    conf = SimpleConfig(field1=40, field2="unsupported")
    config_path = temp_dir / "unsupported.txt"

    with pytest.raises(ValueError, match="Unsupported file extension for saving"):
        conf.save(config_path)

def test_load_unsupported_extension(temp_dir):
    """Tests that loading with an unsupported extension raises a ValueError."""
    # Create a dummy file with an unsupported extension
    config_path = temp_dir / "dummy.txt"
    config_path.write_text("some content")

    with pytest.raises(ValueError, match="Unsupported file extension for loading"):
        SimpleConfig.load(config_path)

def test_nested_config_load_smart_format(temp_dir):
    """Tests that nested configs are correctly loaded using smart format detection."""
    # Create an inner config and save it as a YAML file
    inner_conf = SimpleConfig(field1=50, field2="nested_yaml_inner")
    inner_yaml_path = temp_dir / "nested_inner.yaml"
    inner_conf.save_yaml(inner_yaml_path)

    # Create an outer config that refers to the inner config via the YAML path
    outer_dict = {
        "name": "outer_with_nested_yaml",
        "simple": str(inner_yaml_path) # This should be resolved by smart load
    }
    outer_json_path = temp_dir / "outer_nested.json"
    with open(outer_json_path, "w") as f:
        json.dump(outer_dict, f)

    loaded_outer_conf = NestedConfig.load(outer_json_path)

    assert loaded_outer_conf.name == "outer_with_nested_yaml"
    assert isinstance(loaded_outer_conf.simple, SimpleConfig)
    assert loaded_outer_conf.simple == inner_conf
    assert loaded_outer_conf.simple.uid == inner_conf.uid