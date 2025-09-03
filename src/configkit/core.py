import hashlib
import json
import types
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import (
    Any,
    Self,
    Type,
    dataclass_transform,  # Added Any
    get_args,
    get_origin,
)

import yaml


# A metaclass that automatically applies the @dataclass(frozen=True)
# decorator to any class that uses it, except for the class that has _is_base = True.
@dataclass_transform(frozen_default=True)
class ConfigMeta(type):
    def __new__(cls, name, bases, dct):
        new_class = super().__new__(cls, name, bases, dct)
        # nasty hack. we don't want to decorate the base class itself
        if dct.get("_is_base", False):
            return new_class
        # Apply the dataclass decorator to all subclasses
        return dataclass(frozen=True)(new_class)


# This class now serves as a base class for all configs.
# It contains the serialization and hashing logic and uses the metaclass.
class Config(metaclass=ConfigMeta):
    _is_base = True  # Flag to prevent the metaclass from decorating this class

    def _to_dict(self: Config) -> dict:  # Changed self type from Self to Config
        return asdict(self)

    @property
    def uid(self) -> str:
        config_dict = self._to_dict()
        config_json_string = json.dumps(config_dict, sort_keys=True)
        hasher = hashlib.sha1(config_json_string.encode("utf-8"))
        return hasher.hexdigest()

    def save_json(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(self._to_dict(), f, indent=2)
        print(f"Saved config to {p} as JSON")

    def save_yaml(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            yaml.dump(self._to_dict(), f, indent=2, sort_keys=False)
        print(f"Saved config to {p} as YAML")

    def save(self, path: str | Path) -> None:
        p = Path(path)
        if p.suffix.lower() in (".json", ".jsonc"):
            self.save_json(p)
        elif p.suffix.lower() in (".yaml", ".yml"):
            self.save_yaml(p)
        else:
            raise ValueError(
                f"Unsupported file extension for saving: {p.suffix}. Use .json or .yaml/.yml"
            )

    @classmethod
    def load_json(cls: Type[Self], path: str | Path) -> Self:
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
    def load_yaml(cls: Type[Self], path: str | Path) -> Self:
        p = Path(path)
        with open(p, "r") as f:
            data = yaml.safe_load(f)
        resolved_data = cls._resolve_paths_in_dict(data, cls)
        known_field_names = {f.name for f in fields(cls)}
        filtered_data = {
            k: v for k, v in resolved_data.items() if k in known_field_names
        }
        return cls(**filtered_data)

    @classmethod
    def load(cls: Type[Self], path: str | Path) -> Self:
        p = Path(path)
        if p.suffix.lower() in (".json", ".jsonc"):
            return cls.load_json(p)
        elif p.suffix.lower() in (".yaml", ".yml"):
            return cls.load_yaml(p)
        else:
            raise ValueError(
                f"Unsupported file extension for loading: {p.suffix}. Use .json or .yaml/.yml"
            )

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

            def _get_config_class_from_type(t: Any) -> Type[Config] | None:
                from typing import Union

                # Ensure t is a Type or a Union of Types
                if get_origin(t) in (types.UnionType, Union):
                    type_args = get_args(t)
                elif isinstance(t, type):
                    type_args = (t,)
                else:
                    return None

                for arg in type_args:
                    if isinstance(arg, type) and issubclass(arg, Config):
                        return arg
                return None

            def _resolve_single_value(val: Any, type_hint: Any) -> Any:
                config_class: Type[Config] | None = _get_config_class_from_type(
                    type_hint
                )
                if not config_class:
                    return val
                if isinstance(val, str) and Path(val).exists():
                    # Use the smart load method here
                    return config_class.load(val)
                if isinstance(val, dict):
                    # Recursively call _resolve_paths_in_dict with the correct target_class
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
