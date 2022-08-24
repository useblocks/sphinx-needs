from contextvars import ContextVar
import copy
from datetime import datetime
from enum import Enum, IntEnum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ValidationError, root_validator
from pydantic.fields import Field, ModelField
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx_needs.utils import logger as log


class BaseModelNeeds(BaseModel):
    """
    Custom Base class to support custom validation against all needs.
    
    Uses this approach https://github.com/pydantic/pydantic/issues/1170#issuecomment-575233689
    Other approaches are Python ContextVars which also works. ContextVars however are hard to
    expose to the end users that run custom validators.
    """
    all_needs: Any

    @root_validator()
    def remove_context(cls, values: Dict[str, ModelField]) -> Dict[str, ModelField]:
        """Remove all_needs before others validators run."""
        del values["all_needs"]
        return values


def validator_links(
    value: Union[str, List[str]],
    values: Dict[str, Any],
):
    """
    Check whether a link target
    - is of the right type (str, List[str])
    - has no duplicates
    - exists in the needs dictionary

    The needs dictionary is available as all_needs values as set in BaseModelNeeds.
    """
    if isinstance(value, str):
        # invoked with each_item=true
        links = [value]
    elif isinstance(value, list) and all(isinstance(elem, str) for elem in value):
        # is list of strings
        links = value
        duplicates = [v for v in links if links.count(v) > 1]
        unique_duplicates = list(set(duplicates))
        if unique_duplicates:
            raise ValueError(f"Duplicate link targets '{', '.join(unique_duplicates)}'")
    else:
        raise ValueError(f"Field type is neither str nor List[str]")
    for link in links:
        if link not in values["all_needs"]:
            raise ValueError(f"Cannot find '{link}' in needs dictionary")


def update_config(app: Sphinx, *_args) -> None:
    """
    Derive configurations need_types, need_extra_options and need_extra_links from user models.

    Some thought must go into this, as mentioned configuration parameters feature more information
    such as plantuml colors, incoming/outgoing link names and more.
    Those could be put as a private field into the model class.
    Also a custom field type will be needed to clearly define a needs link field as there
    are other list like need attributes such as sections.
    """


def check_model(env: BuildEnvironment) -> None:
    """
    Check all needs against a user defined pydantic model.

    :param env: Sphinx environment, source of all needs to be made available for validation
    """
    # Only perform calculation if not already done yet
    if env.needs_workflow["model_checked"]:
        return

    needs = env.needs_all_needs
    # all_needs.set(needs)
    pydantic_models = env.config.needs_pydantic_models

    if not pydantic_models:
        # user did not define any models, skip the check
        return

    # build a dictionay to look up user model names
    model_name_2_model = {model.__name__: model for model in pydantic_models}

    logged_types_without_model = set()  # helper to avoid duplicate log output
    all_successful = True
    for need in needs.values():
        try:
            # expected model name is the need type with first letter capitalized (this is how Python class are named)
            expected_pydantic_model_name = need["type"].title()
            if expected_pydantic_model_name in model_name_2_model:
                model = model_name_2_model[expected_pydantic_model_name]
                # get all fields that exist as per the model
                model_fields = [name for name, field in model.__fields__.items() if isinstance(field, ModelField)]
                need_relevant_fields = _clean_empty_unused(need, model_fields, env.config.needs_pydantic_remove_fields)
                model(**need_relevant_fields, all_needs=needs)  # run pydantic
            else:
                if need["type"] not in logged_types_without_model:
                    log.warn(f"Model validation: no model defined for need type '{need['type']}'")
                    logged_types_without_model.add(need["type"])
        except ValidationError as exc:
            all_successful = False
            log.warn(f"Model validation: failed for need {need['id']}")
            log.warn(exc)
            # get field values as pydantic does not publish that in ValidationError
            # in all cases, like for regex checks
            # see https://github.com/pydantic/pydantic/issues/784
            error_fields = set()
            for error in exc.errors():
                for field in error['loc']:
                    if 'regex' in error['type']:
                        if field not in error_fields:
                            log.warn(f"{field}={need[field]}")
                            error_fields.add(field)
    if all_successful:
        log.info("Validation was successful!")

    # Finally set a flag so that this function gets not executed several times
    env.needs_workflow["model_checked"] = True


def _value_allowed(v: Any) -> bool:
    """Check whether a given need field is allowed for validation."""
    if v is None:
        return False
    if isinstance(v, bool):
        # useful for flags such as is_need
        return True
    elif isinstance(v, (str, list)):
        # do not return empty strings or lists - they are never user defined as RST does not support empty options
        return bool(v)
    else:
        # don't return all other types (such as class instances like content_node)
        return False


def _clean_empty_unused(d: Any, model_fields: List[str], remove_fields: List[str]) -> Any:
    """
    Remove need object fields that

    1. are of wrong type (allowed ar str and List[str] and bool)
    1. are empty (those are not relevant anyway as RST does not support empty options)
    2. are in contained in remove_fields (even if not empty like lineno) but not in model_fields

    :param model_fields: list of fields that are contained in the user defined model
    :param remove_fields: list of fields to remove from the dict
    """
    output_dict = {}
    for key, value in d.items():
        if not _value_allowed(value):
            # type check and empty check
            continue
        if key in remove_fields and key not in model_fields:
            continue
        output_dict[key] = value
    return output_dict
