from configkit.core import Config

# --- Correct Usage ---


class MyConfig(Config):
    param_int: int
    param_str: str
    param_bool: bool = True  # Default value


# Test constructor hints
# Should pass mypy
conf_correct = MyConfig(param_int=1, param_str="hello")
conf_correct_with_default = MyConfig(param_int=2, param_str="world", param_bool=False)

# Test method hints (uid, save, load)
uid_val: str = conf_correct.uid
conf_correct.save("test.json")
loaded_conf: MyConfig = MyConfig.load("test.json")  # Assuming test.json exists for mypy


# Test nested config resolution (type checking)
class InnerConfig(Config):
    inner_val: int


class OuterConfig(Config):
    outer_name: str
    nested_conf: InnerConfig


# Direct instantiation
outer_direct = OuterConfig(outer_name="direct", nested_conf=InnerConfig(inner_val=1))

# Loading from dict (mypy should understand this)
outer_from_dict = OuterConfig(
    outer_name="from_dict", nested_conf={"inner_val": 2}
)  # mypy should infer InnerConfig

# Loading from path (mypy should understand this)
# For mypy, we need to mock the file existence or use a Path object
# This is tricky for mypy without a real file. We'll rely on runtime tests for this.
# For mypy, we can just assert the type after load.
# mypy doesn't execute code, so it won't know if "path/to/inner.json" exists.
# We'll focus on the types of the arguments to the constructor.


# --- Intentionally Incorrect Usage (for mypy to catch) ---

# Constructor: Incorrect type for param_int
# type: ignore
conf_wrong_int_type = MyConfig(param_int="not-an-int", param_str="test")

# Constructor: Missing required parameter
# type: ignore
conf_missing_param = MyConfig(param_str="test")

# Constructor: Extra parameter
# type: ignore
conf_extra_param = MyConfig(param_int=1, param_str="test", extra_field="oops")

# Method: Calling non-existent method
# type: ignore
conf_correct.non_existent_method()

# Method: Incorrect return type assignment
# type: ignore
wrong_uid_type: int = conf_correct.uid

# Method: Incorrect argument type for save
# type: ignore
conf_correct.save(123)

# Nested config: Incorrect type for nested_conf
# type: ignore
outer_wrong_nested = OuterConfig(outer_name="bad", nested_conf="not-a-config")

# Nested config: Incorrect type within nested dict
# type: ignore
outer_wrong_nested_dict = OuterConfig(
    outer_name="bad_dict", nested_conf={"inner_val": "wrong_type"}
)

print("Type hint test file created. Run mypy on this file to check for errors.")
