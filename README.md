# configkit: A configuration management library for experiment tracking in python

**Design philosophy**

- A configuration is always bound to a single function and is always passed as the first argument to that function.
- A configuration is represented by a hash of its json-string representation.
- A configuration may be composed of multiple smaller configurations
  - Those smaller configurations may be specified as nested configs directly, or as a path to a file containing the subconfig.
  - A base configuration class should be able to resolve this automatically.
- A configuration is always immutable.

```python
class FirstConfig:
   field1: int
   field2: str
   ...

def do_first_thing(config: FirstConfig):
    ...

class SecondConfig:
    ...
def do_second_thing(config: SecondConfig):
    ...

class BigConfig:
    first: FirstConfig
    second: SecondConfig
def do_big_thing(config: BigConfig):
    ...
```

And I want to be able to do this:

```python
conf1 = FirstConfig(
   ...
)
conf1.save(path1)
conf2 = SecondConfig(
   ...
)
conf2.save(path2)
conf = BigConfig(
first=path1,
second=path2,
)
```

OR

```python
conf = BigConfig(
    first=FirstConfig(...),
    second=SecondConfig(...),
)
```

**Why not hydra?**

- [I prefer not to use YAML](https://ruudvanasseldonk.com/2023/01/11/the-yaml-document-from-hell)
  - Strange handling of numbers
  - Slow load/dump times -- the rules are insanely complex! Not nice when we have 1000s of configs to work with.
- Difficult debugging -- inconsistent behavior between loading a configuration using `@hydra.main` and loading a configuration using `@hydra.utils.instantiate` or `compose`.
