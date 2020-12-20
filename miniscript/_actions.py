# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import abc
import typing

from . import _types

if typing.TYPE_CHECKING:
    from . import _engine


class Result:
    """A result of an action."""

    def __init__(
        self,
        result: typing.Any,
        failure: typing.Optional[str] = None,
    ):
        self.succeeded = failure is None
        self.failed = not self.succeeded
        self.failure = failure
        self.result = result


class When:
    """A when clause."""

    def __init__(
        self,
        engine: '_engine.Engine',
        definition: typing.Union[str, typing.List[str]],
    ):
        if isinstance(definition, str):
            definition = [definition]
        self.definition = definition
        self.engine = engine

    def __call__(self, context: typing.Any) -> bool:
        """Check the condition."""
        return all(self.engine._evaluate(expr, context)
                   for expr in self.definition)


class Action(metaclass=abc.ABCMeta):
    """An abstract base class for an action."""

    required_params: typing.Dict[str, typing.Type] = {}
    """A mapping with required parameters."""

    optional_params: typing.Dict[str, typing.Type] = {}
    """A mapping with optional parameters."""

    list_param: typing.Optional[str] = None
    """A name for the parameter to store if the input is a list."""

    free_form: bool = False
    """Whether this action accepts any arguments.

    Validation for known arguments is still run, and required parameters are
    still required.
    """

    allow_empty: bool = True
    """If no parameters are required, whether to allow empty input."""

    def __init__(
        self,
        engine: '_engine.Engine',
        params: _types.ParamsType,
        name: typing.Optional[str] = None,
        when: typing.Optional[When] = None,
        ignore_errors: bool = False,
        register: typing.Optional[str] = None,
    ):
        if (self.list_param is not None
                and self.list_param not in self.required_params
                and self.list_param not in self.optional_params
                and not self.free_form):
            raise RuntimeError("List parameters must be either a required or "
                               "an optional parameter")

        self.engine = engine
        self._params = params
        self.name = name
        self.when = when
        self.ignore_errors = ignore_errors
        self.register = register
        self._known = set(self.required_params).union(self.optional_params)
        self.validate()

    def validate(self) -> _types.DictType:
        """Validate the passed parameters."""
        params = self._params

        if isinstance(params, list):
            if self.list_param is None:
                raise _types.InvalidDefinition(
                    f"Action {self.name} does not accept a list")
            params = {self.list_param: params}
        elif params is None:
            params = {}

        unknown = set(params).difference(self._known)
        if not self.free_form and unknown:
            raise _types.InvalidDefinition("Parameters %s are not recognized"
                                           % ', '.join(unknown))

        result = {}
        missing = []

        for name, type_ in self.required_params.items():
            try:
                value = params[name]
            except KeyError:
                missing.append(name)
            else:
                try:
                    result[name] = type_(value)
                except (TypeError, ValueError) as exc:
                    raise _types.InvalidDefinition(
                        f"Invalid value for parameter {name} of action "
                        f"{self.name}: {exc}")

        if missing:
            raise _types.InvalidDefinition(
                "Parameters %s are required for action %s",
                ','.join(missing), self.name)

        for name, type_ in self.optional_params.items():
            try:
                value = params[name]
            except KeyError:
                continue

            try:
                result[name] = type_(value)
            except (TypeError, ValueError) as exc:
                raise _types.InvalidDefinition(
                    f"Invalid value for parameter {name} of action "
                    f"{self.name}: {exc}")

        if not result and not self.allow_empty:
            raise _types.InvalidDefinition("At least one of %s is required"
                                           % ', '.join(self.optional_params))

        return result

    def __call__(self, context: typing.Any) -> None:
        """Check conditions and execute the action in the context."""
        if self.when is not None and not self.when(context):
            self.engine.logger.debug("Action %s is skipped", self.name)

        params = self.validate()

        try:
            value = self.execute(params, context)
        except Exception as exc:
            if self.ignore_errors:
                self.engine.logger.warning("Action %s failed: %s (ignoring)",
                                           self.name, exc)
                result = Result(None, f"{exc.__class__.__name__}: {exc}")
            else:
                self.engine.logger.error("Action %s failed: %s",
                                         self.name, exc)
                raise
        else:
            result = Result(value)

        if self.register is not None:
            self.engine.set_var(self.register, result)

    @abc.abstractmethod
    def execute(
        self,
        params: _types.DictType,
        context: typing.Any
    ) -> _types.JsonType:
        """Execute the action.

        :returns: The value stored as a result in ``register`` is set.
        """


class Block(Action):
    """Grouping of actions."""

    required_params = {"tasks": list}
    list_param = "tasks"

    def validate(self) -> _types.DictType:
        tasks = super().validate()["tasks"]
        tasks = [self.engine._load_action(task) for task in tasks]
        return {"tasks": tasks}

    def execute(self, params: _types.DictType, context: typing.Any) -> None:
        for task in params["tasks"]:
            task(context)


class Log(Action):
    """Log something."""

    optional_params = {
        key: str for key in ("debug", "info", "warning", "error")}

    allow_empty = False

    def execute(self, params: _types.DictType, context: typing.Any) -> None:
        for key, value in params.items():
            getattr(self.engine.logger, key)(value)


class SetVar(Action):
    """Set some variables."""

    free_form = True

    def execute(self, params: _types.DictType, context: typing.Any) -> None:
        for key, value in params.items():
            self.engine.set_var(key, value)