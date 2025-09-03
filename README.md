# configkit: A configuration management library for experiment tracking in python

**Design philosophy**

- A configuration is always bound to a single function and is always passed as the first argument to that function.
- A configuration is represented by a hash of its json-string representation.
- A configuration may be composed of multiple smaller configurations
  - Those smaller configurations may be specified as nested configs directly, or as a path to a file containing the subconfig.
  - A base configuration class should be able to resolve this automatically.
- A configuration is always immutable.

**Some examples**

```python
class FirstConfig:
   field1: int
   field2: str
   ...

def do_first_thing(config: FirstConfig):
    ...

class SecondConfig:
    field3: tuple[int]
    ...
def do_second_thing(config: SecondConfig):
    ...

class BigConfig:
    first: FirstConfig
    second: SecondConfig
def do_big_thing(config: BigConfig):
    do_first_thing(config.first)
    do_second_thing(config.second)
    ...
```

And I want to be able to do this:

```python
conf = BigConfig(
    first=FirstConfig(...),
    second=SecondConfig(...),
)

same_conf = BigConfig(
    first = {"field1": 123, "field2": "hello"},
    second = {"field3" (1,2,3)}
)
```

**Why not hydra?**

- [I prefer not to use YAML](https://ruudvanasseldonk.com/2023/01/11/the-yaml-document-from-hell)
  - Strange handling of numbers
  - Slow load/dump times -- the rules are insanely complex! Not nice when we have 1000s of configs to work with.
- Difficult debugging -- inconsistent behavior between loading a configuration using `@hydra.main` and loading a configuration using `@hydra.utils.instantiate` or `compose`.
