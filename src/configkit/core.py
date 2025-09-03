import hashlib
import json
import sys
import types
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import (
    Any,
    Type,
    Union,
    dataclass_transform,
    get_args,
    get_origin,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

import yaml


@dataclass_transform(frozen_default=True)
class ConfigMeta(type):
    def __new__(cls, name, bases, dct):
        new_class = super().__new__(cls, name, bases, dct)
        if dct.get("_is_base", False):
            return new_class
        return dataclass(frozen=True)(new_class)


class Config(metaclass=ConfigMeta):
    _is_base = True

    def _to_dict(self) -> dict:
        return asdict(self)

    @property
    def uid(self) -> str:
        config_dict = self._to_dict()
        config_json_string = json.dumps(config_dict, sort_keys=True)
        hasher = hashlib.sha1(config_json_string.encode("utf-8"))
        return hasher.hexdigest()

    def save_json(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump(self._to_dict(), f, indent=2)
        print(f"Saved config to {p} as JSON")

    def save_yaml(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            yaml.dump(self._to_dict(), f, indent=2, sort_keys=False)
        print(f"Saved config to {p} as YAML")

    def save(self, path: Union[str, Path]) -> None:
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
    def load_json(cls: Type[Self], path: Union[str, Path]) -> Self:
        p = Path(path)
        with open(p, "r") as f:
            data = json.load(f)
        return cls._from_dict(data)

    @classmethod
    def load_yaml(cls: Type[Self], path: Union[str, Path]) -> Self:
        p = Path(path)
        with open(p, "r") as f:
            data = yaml.safe_load(f)
        return cls._from_dict(data)

    @classmethod
    def load(cls: Type[Self], path: Union[str, Path]) -> Self:
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
    def _from_dict(cls: Type[Self], data: dict) -> Self:
        resolved_data = cls._resolve_nested_configs(data, cls)
        known_field_names = {f.name for f in fields(cls)}
        filtered_data = {
            k: v for k, v in resolved_data.items() if k in known_field_names
        }
        return cls(**filtered_data)

    @classmethod
    def _resolve_nested_configs(cls, data: dict, target_class: type) -> dict:
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
            resolved_data[key] = cls._convert_to_config_if_nested(value, field_type)

        return resolved_data

    @classmethod
    def _convert_to_config_if_nested(cls, value: Any, type_hint: Any) -> Any:
        origin, type_args = get_origin(type_hint), get_args(type_hint)

        if origin in (list, types.UnionType, Union):
            if origin is list and type_args:
                return [
                    cls._convert_to_config_if_nested(item, type_args[0])
                    for item in value
                    if isinstance(value, list)
                ]
            if origin in (types.UnionType, Union):
                for arg in type_args:
                    try:
                        # Attempt to convert to config if the arg is a Config subclass
                        return cls._convert_to_config_if_nested(value, arg)
                    except (TypeError, ValueError):
                        continue

        if origin is dict and len(type_args) > 1:
            return {
                k: cls._convert_to_config_if_nested(v, type_args[1])
                for k, v in value.items()
                if isinstance(value, dict)
            }

        if isinstance(type_hint, type) and issubclass(type_hint, Config):
            if isinstance(value, dict):
                # Recursively call _from_dict for nested Configs
                return type_hint._from_dict(value)

        return value