import hashlib
import json
import types
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Type, dataclass_transform, get_args, get_origin


# A metaclass that automatically applies the @dataclass(frozen=True)
# decorator to any class that uses it, except for the class that has _is_base = True.
@dataclass_transform(frozen_default=True)
class ConfigMeta(type):
    def __new__(cls, name, bases, dct):
        new_class = super().__new__(cls, name, bases, dct)
        # We don't want to decorate the base class itself
        if dct.get("_is_base", False):
            return new_class
        # Apply the dataclass decorator to all subclasses
        return dataclass(frozen=True)(new_class)


# This class now serves as a base class for all configs.
# It contains the serialization and hashing logic and uses the metaclass.
class ConfigBase(metaclass=ConfigMeta):
    _is_base = True  # Flag to prevent the metaclass from decorating this class

    def _to_dict(self) -> dict:
        return asdict(self)

    @property
    def uid(self) -> str:
        config_dict = self._to_dict()
        config_json_string = json.dumps(config_dict, sort_keys=True)
        hasher = hashlib.sha1(config_json_string.encode("utf-8"))
        return hasher.hexdigest()

    def save(self, path: str | Path):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(self._to_dict(), f, indent=2)
        print(f"Saved config to {p}")

    @classmethod
    def load(cls: Type["Self"], path: str | Path) -> "Self":
        p = Path(path)
        with open(p, "r") as f:
            data = json.load(f)
        resolved_data = cls._resolve_paths_in_dict(data, cls)
        known_field_names = {f.name for f in fields(cls)}
        filtered_data = {
            k: v for k, v in resolved_data.items() if k in known_field_names
        }
        return cls(**filtered_data)

    @classmethod
    def _resolve_paths_in_dict(cls, data: dict, target_class: type) -> dict:
        resolved_data = {}
        try:
            class_fields = {f.name: f.type for f in fields(target_class)}
        except TypeError:
            return data
        for key, value in data.items():
            if key not in class_fields:
                resolved_data[key] = value
                continue
            field_type = class_fields[key]

            def _get_config_class_from_type(t):
                from typing import Union

                type_args = (
                    get_args(t) if get_origin(t) in (types.UnionType, Union) else (t,)
                )
                for arg in type_args:
                    if isinstance(arg, type) and issubclass(arg, ConfigBase):
                        return arg
                return None

            def _resolve_single_value(val, type_hint):
                config_class = _get_config_class_from_type(type_hint)
                if not config_class:
                    return val
                if isinstance(val, str) and Path(val).exists():
                    return config_class.load(val)
                if isinstance(val, dict):
                    resolved_nested_dict = cls._resolve_paths_in_dict(val, config_class)
                    return config_class(**resolved_nested_dict)
                return val

            origin, type_args = get_origin(field_type), get_args(field_type)
            if origin is list and type_args:
                resolved_data[key] = (
                    [_resolve_single_value(item, type_args[0]) for item in value]
                    if isinstance(value, list)
                    else value
                )
            elif origin is dict and len(type_args) > 1:
                resolved_data[key] = (
                    {
                        k: _resolve_single_value(v, type_args[1])
                        for k, v in value.items()
                    }
                    if isinstance(value, dict)
                    else value
                )
            else:
                resolved_data[key] = _resolve_single_value(value, field_type)
        return resolved_data
