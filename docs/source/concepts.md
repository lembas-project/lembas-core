# Concepts

## Case handlers

`lembas` represents parametrized **types** of analyses via the concept of a case handler.
A case handler is analogous to a "workflow" in other frameworks, and is a collection of **steps** organized to attain a single goal.

For example, consider the following case handler:

```python
from lembas import Case, InputParameter, step

class HelloCase(Case):
    name = InputParameter(default="Anonymous")

    @step
    def say_hello(self):
        print(f"Hello {self.name}!")
```

The case handler may be run by constructing an instance and calling the [`run()`](lembas.core.Case.run) method:

```python
case = HelloCase()
case.run()  # prints "Hello Anonymous!"

case = HelloCase(name="Mike")
case.run()  # prints "Hello Mike!"
```

```{note}
In this case, `name` is an optional parameter because a `default` is defined
```

That is not very interesting.
Let's create and run multiple cases in one go!

The container for a list of cases is [`CaseList`](lembas.CaseList), and we can quickly add a parameter sweep.
The call to [`cases.add_cases_by_parameter_sweep()`](lembas.CaseList.add_cases_by_parameter_sweep) is a shortcut for adding a sweep of cases across multiple iterables.
For a single parameter, we can iterate over `name` by passing in a list, and the call to [`cases.run_all()`](lembas.CaseList.run_all) will run each case in succession.

```python
from lembas import CaseList

cases = CaseList()
cases.add_cases_by_parameter_sweep(
    HelloCase,
    name=["Rivers", "Brian", "Scott", "Pat"],
)
cases.run_all()  # prints "Hello Rivers!", "Hello Brian!", ...
```
