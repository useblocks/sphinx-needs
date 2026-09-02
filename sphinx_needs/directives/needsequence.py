from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import NeedsSequenceType, SphinxNeedsData
from sphinx_needs.diagrams_common import (
    DiagramBase,
    add_config,
    create_legend,
    get_debug_container,
    get_filter_para,
    no_plantuml,
    set_plantuml_paths,
)
from sphinx_needs.directives.utils import (
    no_needs_found_paragraph,
    report_max_items,
)
from sphinx_needs.filter_common import (
    FilterBase,
    filter_single_need,
    resolve_max_items,
)
from sphinx_needs.logging import get_logger, log_warning
from sphinx_needs.need_item import NeedItem
from sphinx_needs.utils import add_doc, remove_node_from_tree
from sphinx_needs.views import NeedsView

logger = get_logger(__name__)


class Needsequence(nodes.General, nodes.Element):
    pass


class NeedsequenceDirective(FilterBase, DiagramBase, Exception):
    """
    Directive to get sequence diagrams.
    """

    optional_arguments = 1
    final_argument_whitespace = True
    option_spec = {
        "start": directives.unchanged,
        "link_types": directives.unchanged,
        "max_items": directives.nonnegative_int,
        # ubCode compatibility: accepted and ignored by Sphinx-Needs.
        "width": directives.unchanged,
        "height": directives.unchanged,
    }

    # Update the options_spec with values defined in the FilterBase class
    option_spec.update(FilterBase.base_option_spec)
    option_spec.update(DiagramBase.base_option_spec)

    def run(self) -> Sequence[nodes.Node]:
        env = self.env

        _, targetid, targetnode = self.create_target("needsequence")

        start = self.options.get("start")
        if start is None or len(start.strip()) == 0:
            raise NeedSequenceException(
                "No valid start option given for needsequence. "
                f"See file {env.docname}:{self.lineno}"
            )

        attributes: NeedsSequenceType = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "start": self.options.get("start", ""),
            "max_items": self.options.get("max_items"),
            **self.collect_filter_attributes(),
            **self.collect_diagram_attributes(),
        }
        node = Needsequence("", **attributes)
        self.set_source_info(node)

        add_doc(env, env.docname)

        return [targetnode, node]


def process_needsequence(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    # Replace all needsequence nodes with a list of the collected needs.
    env = app.env
    needs_data = SphinxNeedsData(env)
    needs_schema = needs_data.get_schema()
    all_needs_dict = needs_data.get_needs_view()

    needs_config = NeedsSphinxConfig(env.config)
    include_needs = needs_config.include_needs
    link_type_names = [name.upper() for name in needs_schema.iter_link_field_names()]
    needs_types = needs_config.types

    # NEEDSEQUENCE
    # for node in doctree.findall(Needsequence):
    for node in found_nodes:
        if not include_needs:
            remove_node_from_tree(node)
            continue

        current_needsequence: NeedsSequenceType = node.attributes

        option_link_types = [
            link.upper() for link in current_needsequence["link_types"]
        ]
        for lt in option_link_types:
            if lt not in link_type_names:
                log_warning(
                    logger,
                    "Unknown link type {link_type} in needsequence {flow}. Allowed values:"
                    " {link_types}".format(
                        link_type=lt,
                        flow=current_needsequence["target_id"],
                        link_types=",".join(link_type_names),
                    ),
                    "needsequence",
                    location=node,
                )

        content = []
        try:
            if "sphinxcontrib.plantuml" not in app.extensions:
                raise ImportError
            from sphinxcontrib.plantuml import generate_name, plantuml
        except ImportError:
            no_plantuml(node)
            continue

        plantuml_block_text = ".. plantuml::\n\n   @startuml   @enduml"
        puml_node = plantuml(plantuml_block_text)

        # Add source origin
        puml_node.line = current_needsequence["lineno"]
        puml_node.source = env.doc2path(current_needsequence["docname"])

        puml_node["uml"] = "@startuml\n"

        # Adding config
        config = current_needsequence["config"]
        puml_node["uml"] += add_config(config)

        start_needs_id = [
            x.strip() for x in re.split(";|,", current_needsequence["start"])
        ]
        if len(start_needs_id) == 0:
            # TODO this should be a warning (and not tested)
            raise NeedSequenceException(
                "No start-id set for needsequence"
                f" docname {current_needsequence['docname']}"
                f":{current_needsequence['lineno']}"
            )

        puml_node["uml"] += "\n' Nodes definition \n\n"

        # Add  start participants
        p_string = ""
        c_string = ""
        # the cap counts messages (arrows), and is shared by all start needs,
        # since it applies to the diagram as a whole
        counter = _MessageCounter(
            resolve_max_items(current_needsequence.get("max_items"), needs_config)
        )
        for need_id in start_needs_id:
            try:
                need = all_needs_dict[need_id.strip()]
            except KeyError:
                raise NeedSequenceException(
                    "Given {} in needsequence unknown. File {}:{}".format(
                        need_id,
                        current_needsequence["docname"],
                        current_needsequence["lineno"],
                    )
                )

            # Add children of participants
            _msg_receiver_needs, p_string_new, c_string_new = get_message_needs(
                app,
                need,
                current_needsequence["link_types"],
                all_needs_dict,
                filter=current_needsequence["filter"],
                counter=counter,
                origin_docname=current_needsequence["docname"],
            )
            p_string += p_string_new
            c_string += c_string_new

        p_string += counter.declarations_to_restore()

        puml_node["uml"] += p_string

        puml_node["uml"] += "\n' Connection definition \n\n"
        puml_node["uml"] += c_string

        # Create a legend
        if current_needsequence["show_legend"]:
            puml_node["uml"] += create_legend(needs_types)

        puml_node["uml"] += "\n@enduml"
        set_plantuml_paths(puml_node, env, current_needsequence["docname"])

        scale = int(current_needsequence["scale"])
        # if scale != 100:
        puml_node["scale"] = scale

        puml_node = nodes.figure("", puml_node)

        if current_needsequence["align"]:
            puml_node["align"] = current_needsequence["align"]
        else:
            puml_node["align"] = "center"

        if current_needsequence["caption"]:
            # Make the caption to a link to the original file.
            try:
                if "SVG" in app.config.plantuml_output_format.upper():
                    file_ext = "svg"
                else:
                    file_ext = "png"
            except Exception:
                file_ext = "png"

            gen_flow_link = generate_name(app, puml_node.children[0], file_ext)
            current_file_parts = fromdocname.split("/")
            subfolder_amount = len(current_file_parts) - 1
            img_locaton = (
                "../" * subfolder_amount + "_images/" + gen_flow_link[0].split("/")[-1]
            )
            flow_ref = nodes.reference(
                "t", current_needsequence["caption"], refuri=img_locaton
            )
            puml_node += nodes.caption("", "", flow_ref)

        # Add lineno to node
        puml_node.line = current_needsequence["lineno"]

        content.append(puml_node)

        if (
            len(c_string) == 0 and p_string.count("participant") == 1
        ):  # no connections and just one (start) participant
            content = [
                (no_needs_found_paragraph(current_needsequence.get("filter_warning")))  # type: ignore[list-item]
            ]
        if counter.shown < counter.total:
            content.append(
                report_max_items(  # type: ignore[arg-type]
                    counter.shown,
                    counter.total,
                    origin="needsequence",
                    location=node,
                    unit="messages",
                )
            )
        if current_needsequence["show_filters"]:
            content.append(get_filter_para(current_needsequence))  # type: ignore[arg-type]

        if current_needsequence["debug"]:
            content += get_debug_container(puml_node)  # type: ignore[arg-type]

        node.replace_self(content)


@dataclass
class _MessageCounter:
    """Counts the messages of a sequence diagram, against the ``max_items`` cap.

    The walk keeps counting messages after the cap has been reached,
    so that the truncation notice can report an honest total.
    """

    limit: int
    """The maximum number of messages to draw, zero or less meaning no limit."""
    total: int = 0
    """The number of messages the walk would draw, were there no limit."""
    shown: int = 0
    """The number of messages the walk actually drew."""
    drawn_ids: set[str] = field(default_factory=set)
    """The ids of the participants that a drawn message refers to."""
    suppressed: list[tuple[str, str]] = field(default_factory=list)
    """Participant declarations the cap suppressed, in walk order, as (id, line)."""

    @property
    def has_room(self) -> bool:
        """Whether a further message may still be drawn."""
        return self.limit <= 0 or self.shown < self.limit

    def add_message(self, sender_id: str, receiver_id: str) -> bool:
        """Count a message that the walk would draw.

        :param sender_id: the id of the need the message is drawn from.
        :param receiver_id: the id of the need the message is drawn to.

        :return: True if the message is within the cap and should be drawn.
        """
        self.total += 1
        if not self.has_room:
            return False
        self.shown += 1
        self.drawn_ids.update((sender_id, receiver_id))
        return True

    def declarations_to_restore(self) -> str:
        """The suppressed declarations of participants that a drawn message refers to.

        The cap is exhausted *by* the last message that is drawn, so the participant on
        the receiving end of it reaches its declaration after there is no room left.
        Without restoring it, PlantUML auto-creates that lifeline and labels it with the
        raw need id, whilst every other lifeline shows a title -- truncation would then
        have altered a participant that is still drawn, rather than only removing ones
        that are not.

        Restoring is strictly additive, and only ever undoes the cap's own suppression:
        nothing is suppressed when there is no limit, and a suppressed declaration is
        restored only if a message that was drawn refers to it.

        :return: the declarations to append, in walk order.
        """
        return "".join(line for id_, line in self.suppressed if id_ in self.drawn_ids)


def get_message_needs(
    app: Sphinx,
    sender: NeedItem,
    link_types: list[str],
    all_needs_dict: NeedsView,
    tracked_receivers: list[str] | None = None,
    filter: str | None = None,
    *,
    counter: _MessageCounter,
    origin_docname: str | None = None,
) -> tuple[dict[str, dict[str, Any]], str, str]:
    """Walk the messages sent by ``sender``, drawing each receiver that passes ``filter``.

    :param origin_docname: The document the needsequence is written in, so that a
        ``filter`` may test the receiver against it with ``c.this_doc()``.
    """
    msg_needs: list[dict[str, Any]] = []
    if tracked_receivers is None:
        tracked_receivers = []
    for link_type in link_types:
        msg_needs += [all_needs_dict[x] for x in sender[link_type]]  # type: ignore[misc]

    messages: dict[str, dict[str, Any]] = {}
    p_string = ""
    c_string = ""
    for msg_need in msg_needs:
        messages[msg_need["id"]] = {
            "id": msg_need["id"],
            "title": msg_need["title"],
            "receivers": {},
        }
        if sender["id"] not in tracked_receivers:
            declaration = 'participant "{}" as {}\n'.format(
                sender["title"], sender["id"]
            )
            if counter.has_room:
                p_string += declaration
            else:
                # a participant is only declared whilst the cap has room, so that
                # truncation can never add a participant that sends no message; it is
                # held here in case a message that was drawn turns out to refer to it
                counter.suppressed.append((sender["id"], declaration))
            # the sender is tracked even when it was not declared, so that the shape
            # of the walk, and hence the message total, does not depend on the cap
            tracked_receivers.append(sender["id"])
        for link_type in link_types:
            receiver_ids = msg_need[link_type]
            for rec_id in receiver_ids:
                if filter and not filter_single_need(
                    all_needs_dict[rec_id],
                    NeedsSphinxConfig(app.config),
                    filter,
                    needs=all_needs_dict.values(),
                    origin_docname=origin_docname,
                ):
                    continue

                rec_data = {
                    "id": rec_id,
                    "title": all_needs_dict[rec_id]["title"],
                    "messages": [],
                }

                if counter.add_message(sender["id"], rec_id):
                    c_string += "{} -> {}: {}\n".format(
                        sender["id"], rec_data["id"], msg_need["title"]
                    )

                if rec_id not in tracked_receivers:
                    rec_messages, p_string_new, c_string_new = get_message_needs(
                        app,
                        all_needs_dict[rec_id],
                        link_types,
                        all_needs_dict,
                        tracked_receivers,
                        filter=filter,
                        counter=counter,
                        origin_docname=origin_docname,
                    )
                    p_string += p_string_new
                    c_string += c_string_new

                    rec_data["messages"] = rec_messages

                messages[msg_need["id"]]["receivers"][rec_id] = rec_data

    return messages, p_string, c_string


class NeedSequenceException(BaseException):
    """Errors during Sequence handling"""
