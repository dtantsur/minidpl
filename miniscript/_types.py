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

import typing


DictType = typing.Dict[str, typing.Any]


JsonType = typing.Union[
    DictType,
    typing.List,
    str,
    int,
    bool,
    None
]


ParamsType = typing.Union[
    typing.Dict[str, JsonType],
    typing.List[JsonType],
    None
]


class Error(Exception):
    """Base class for all errors."""


class InvalidScript(Error, TypeError):
    """The script definition is invalid."""


class InvalidDefinition(Error, ValueError):
    """A definition of an action is invalid."""


class UnknownAction(InvalidDefinition):
    """An action is not known."""