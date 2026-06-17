# Common Code Quality and Style Patterns

This reference document explains the common issues detected by the Code Reviewer skill and how to fix them.

## 1. Mutable Default Arguments

### The Problem
Using mutable objects (like lists, dictionaries, or sets) as default values in function definitions can lead to unexpected behavior because the default value is created **once** when the function is defined, and then shared across all subsequent calls.

```python
# Bad Pattern
def append_to_list(element, my_list=[]):
    my_list.append(element)
    return my_list

print(append_to_list(1))  # [1]
print(append_to_list(2))  # [1, 2] -- shared state!
```

### The Fix
Use `None` as the default value and instantiate the mutable object inside the function body.

```python
# Good Pattern
def append_to_list(element, my_list=None):
    if my_list is None:
        my_list = []
    my_list.append(element)
    return my_list
```

---

## 2. Bare/Empty Except Blocks

### The Problem
Catching all exceptions (`except:` or `except Exception:`) and ignoring them (`pass` or simple comments) hides bugs and makes debugging extremely difficult, as critical failures (like `KeyboardInterrupt` or syntax issues) are suppressed.

```python
# Bad Pattern
try:
    result = perform_calculation()
except Exception:
    pass
```

### The Fix
Catch specific exceptions whenever possible. If you must catch all exceptions, at least log the exception or re-raise it.

```python
# Good Pattern
import logging

try:
    result = perform_calculation()
except ValueError as e:
    logging.warning(f"Invalid value: {e}")
    result = 0
```

---

## 3. Shadowing Built-in Names

### The Problem
Defining variables, parameters, or functions that override Python's built-in namespace (e.g., `id`, `type`, `list`, `dict`, `str`, `sum`) can break code that relies on those built-ins and cause confusing errors.

```python
# Bad Pattern
def process_data(id, list):
    # 'id' and 'list' are shadowed
    for item in list:
        print(id, item)
```

### The Fix
Rename the variables/parameters to be more descriptive or append a trailing underscore (e.g., `item_id`, `items`, `list_`).

```python
# Good Pattern
def process_data(item_id, items):
    for item in items:
        print(item_id, item)
```

---

## 4. Leftover Debug Triggers

### The Problem
Leftover print statements, `breakpoint()`, or `pdb.set_trace()` can halt execution in production environments or flood logging systems with unstructured text.

```python
# Bad Pattern
def calculate_freight(route):
    print("DEBUG ROUTE:", route)  # Leftover print
    breakpoint()                  # Halts execution!
    return route.cost * 1.1
```

### The Fix
Use proper structured logging instead of prints, and remove breakpoint calls before committing.

```python
# Good Pattern
import logging

logger = logging.getLogger(__name__)

def calculate_freight(route):
    logger.debug(f"Calculating freight for route: {route}")
    return route.cost * 1.1
```

---

## 5. High Parameter Counts and Long Functions

### The Problem
Functions with more than 5 parameters or exceeding 50 lines are generally harder to read, maintain, and test.

### The Fix
- **High Parameters**: Pass an object, dataclass, or dictionary representing the data.
- **Long Functions**: Apply the "Extract Method" refactoring pattern to break the code into smaller, single-purpose functions.
