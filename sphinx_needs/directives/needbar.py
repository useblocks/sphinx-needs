from __future__ import annotations

import hashlib
import math
from typing import Sequence

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx

from sphinx_needs.config import NeedsSphinxConfig
from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.filter_common import FilterBase, filter_needs, prepare_need_list
from sphinx_needs.logging import get_logger
from sphinx_needs.utils import (
    add_doc,
    import_matplotlib,
    remove_node_from_tree,
    save_matplotlib_figure,
)

logger = get_logger(__name__)


class Needbar(nodes.General, nodes.Element):
    pass


class NeedbarDirective(FilterBase):
    """
    Directive to plot diagrams with the help of matplotlib

    .. versionadded: 0.7.5
    """

    has_content = True

    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    option_spec = {
        "style": directives.unchanged_required,
        "colors": directives.unchanged_required,
        "text_color": directives.unchanged_required,
        "x_axis_title": directives.unchanged_required,
        "xlabels": directives.unchanged_required,
        "xlabels_rotation": directives.unchanged_required,
        "y_axis_title": directives.unchanged_required,
        "ylabels": directives.unchanged_required,
        "ylabels_rotation": directives.unchanged_required,
        "separator": directives.unchanged_required,
        "legend": directives.flag,
        "stacked": directives.flag,
        "show_sum": directives.flag,
        "show_top_sum": directives.flag,
        "sum_rotation": directives.unchanged_required,
        "transpose": directives.flag,
        "horizontal": directives.flag,
    }

    # Algorithm:
    # 1. define constants
    # 2. Stores infos for needbar
    def run(self) -> Sequence[nodes.Node]:
        # 1. define constants
        env = self.env

        id = env.new_serialno("needbar")
        targetid = f"needbar-{env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])
        error_id = f"Needbar - file '{env.docname}' - line '{self.lineno}'"

        self.assert_has_content()
        content = self.content

        title = self.arguments[0].strip() if self.arguments else None

        text_color = self.options.get("text_color")
        if text_color:
            text_color = text_color.strip()

        style = self.options.get("style")
        matplotlib = import_matplotlib()
        style = (
            style.strip()
            if style
            else (matplotlib.style.use("default") if matplotlib else "default")
        )

        legend = "legend" in self.options

        colors = self.options.get("colors")
        if colors:
            colors = [x.strip() for x in colors.split(",")]

        x_axis_title = self.options.get("x_axis_title")
        if x_axis_title:
            x_axis_title = x_axis_title.strip()
        xlabels = self.options.get("xlabels")
        if xlabels:
            xlabels = [x.strip() for x in xlabels.split(",")]
        xlabels_rotation = self.options.get("xlabels_rotation")
        if xlabels_rotation:
            xlabels_rotation = xlabels_rotation.strip()

        y_axis_title = self.options.get("y_axis_title")
        if y_axis_title:
            y_axis_title = y_axis_title.strip()
        ylabels = self.options.get("ylabels")
        if ylabels:
            ylabels = [y.strip() for y in ylabels.split(",")]
        ylabels_rotation = self.options.get("ylabels_rotation")
        if ylabels_rotation:
            ylabels_rotation = ylabels_rotation.strip()

        separator = self.options.get("separator")
        if not separator:
            separator = ","

        stacked = "stacked" in self.options
        show_sum = "show_sum" in self.options
        show_top_sum = "show_top_sum" in self.options
        sum_rotation = self.options.get("sum_rotation")
        if sum_rotation:
            sum_rotation = sum_rotation.strip()
        transpose = "transpose" in self.options
        horizontal = "horizontal" in self.options

        # 2. Stores infos for needbar
        data = SphinxNeedsData(self.env).get_or_create_bars()
        data[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_id": targetid,
            "error_id": error_id,
            "title": title,
            "content": content,
            "legend": legend,
            "x_axis_title": x_axis_title,
            "xlabels": xlabels,
            "xlabels_rotation": xlabels_rotation,
            "y_axis_title": y_axis_title,
            "ylabels": ylabels,
            "ylabels_rotation": ylabels_rotation,
            "separator": separator,
            "stacked": stacked,
            "show_sum": show_sum,
            "show_top_sum": show_top_sum,
            "sum_rotation": sum_rotation,
            "transpose": transpose,
            "horizontal": horizontal,
            "style": style,
            "colors": colors,
            "text_color": text_color,
        }

        add_doc(env, env.docname)

        bar_node = Needbar("")
        self.set_source_info(bar_node)

        return [targetnode, bar_node]


# Algorithm:
# 1. define constants
# 2. pre process data
# 3. process the labels (maybe from content)
# 4. transpose the data if needed
# 5. process content
# 6. calculate index according to configuration and content size
# 7. styling and coloring
# 8. create figure
# 9. final storage
# 10. cleanup matplotlib
def process_needbar(
    app: Sphinx,
    doctree: nodes.document,
    fromdocname: str,
    found_nodes: list[nodes.Element],
) -> None:
    env = app.env
    needs_data = SphinxNeedsData(env)
    needs_config = NeedsSphinxConfig(env.config)

    matplotlib = import_matplotlib()

    if matplotlib is None and found_nodes and needs_config.include_needs:
        logger.warning(
            "Matplotlib is not installed and required by needbar. "
            "Install with `sphinx-needs[plotting]` to use. [needs.mpl]",
            once=True,
            type="needs",
            subtype="mpl",
        )

    # NEEDFLOW
    # for node in doctree.findall(Needbar):
    for node in found_nodes:
        if not needs_config.include_needs:
            remove_node_from_tree(node)
            continue

        id = node.attributes["ids"][0]
        current_needbar = needs_data.get_or_create_bars()[id]

        if matplotlib is None:
            message = "Matplotlib missing for needbar plot"
            if current_needbar["title"]:
                message += f" {current_needbar['title']!r}"
            node.replace_self(nodes.error("", nodes.paragraph(text=message)))
            continue

        # 1. define constants
        error_id = current_needbar["error_id"]

        separator = current_needbar["separator"]
        if not separator:
            separator = ","

        # 2. pre process data
        # local_data: only valid data be stored, e.g. get ried of xlabels or ylabels content
        local_data = []
        test_columns_length = 0
        content = current_needbar["content"]
        for x in range(len(content)):
            row_data = content[x].split(separator)
            local_data.append(row_data)

            if x == 0:
                test_columns_length = len(row_data)
            else:
                # We can only process content with the same lenght for each line
                if test_columns_length != len(row_data):
                    raise Exception(
                        f"{error_id}: each content line must have the same length"
                    )

        # 3. process the labels (maybe from content)
        xlabels = current_needbar["xlabels"]
        xlabels_in_content = bool(
            xlabels and len(xlabels) >= 1 and xlabels[0] == "FROM_DATA"
        )
        ylabels = current_needbar["ylabels"]
        ylabels_in_content = bool(
            ylabels and len(ylabels) >= 1 and ylabels[0] == "FROM_DATA"
        )

        if xlabels_in_content:
            # get xlabels from content => first row in content
            xlabels = local_data[0]
            local_data = local_data[1:]  # remove the first row from further processing
            if ylabels_in_content:  # we have a ylabels in the content:
                xlabels = xlabels[1:]  # first element (0) in the row has to be ignored
            xlabels = [x.strip() for x in xlabels]
        if not xlabels:  # xlabels not been fetched from parameter or content
            xlabels = [str(1 + x) for x in range(len(local_data[0]))]

        if ylabels_in_content:
            # get ylabels from content => first dataset in each row
            ylabels = []
            new_local_data = []
            for line in local_data:
                ylabels.append(line[0])  # fetch ylabels values from first rows
                new_local_data.append(line[1:])
            local_data = new_local_data
            ylabels = [y.strip() for y in ylabels]
        if not ylabels:  # ylabels not been fetched from parameter or content
            ylabels = [str(1 + y) for y in range(len(local_data))]

        # ensure length of xlabels == content columns
        if not len(xlabels) == len(local_data[0]):
            raise Exception(
                f"{error_id} length of xlabels: {len(xlabels)} is not equal with sum of columns: {len(local_data[0])}"
            )

        # ensure length of ylabels == content rows
        if not len(ylabels) == len(local_data):
            raise Exception(
                f"{error_id} length of ylabels: {len(ylabels)} is not equal with sum of rows: {len(local_data)}"
            )

        # 4. transpose the data if needed
        if current_needbar["transpose"]:
            local_data = [
                [local_data[j][i] for j in range(len(local_data))]
                for i in range(len(local_data[0]))
            ]
            tmp = ylabels
            ylabels = xlabels
            xlabels = tmp

        # 5. process content
        local_data_number = []
        need_list = list(
            prepare_need_list(needs_data.get_or_create_needs().values())
        )  # adds parts to need_list

        for line in local_data:
            line_number = []
            for element in line:
                element = element.strip()
                if element.isdigit():
                    line_number.append(float(element))
                else:
                    result = len(
                        filter_needs(need_list, needs_config, element, location=node)
                    )
                    line_number.append(float(result))
            local_data_number.append(line_number)

        # 6. calculate index according to configuration and content size
        index = []
        for row in range(len(local_data_number)):
            _line = []
            for column in range(len(local_data_number[0])):
                if current_needbar["stacked"]:
                    _line.append(column)
                else:
                    value = row + column * len(local_data_number) + column
                    _line.append(value)
            index.append(_line)

        # 7. styling and coloring
        style_previous_to_script_execution = matplotlib.rcParams
        # Set matplotlib style
        if current_needbar["style"]:
            matplotlib.style.use(current_needbar["style"])
        else:
            # It is necessary to set default style, otherwise the old styling will be used again.
            matplotlib.style.use("default")

        # set text colors
        if current_needbar["text_color"]:
            text_color = current_needbar["text_color"].strip()
            matplotlib.rcParams["text.color"] = text_color
            matplotlib.rcParams["axes.labelcolor"] = text_color
            try:
                matplotlib.rcParams["xtick.labelcolor"] = text_color
                matplotlib.rcParams["ytick.labelcolor"] = text_color
            except KeyError:
                # labelcolor is not support in this matplotlib version. Use color instead.
                matplotlib.rcParams["xtick.color"] = text_color
                matplotlib.rcParams["ytick.color"] = text_color

        # get bar colors
        colors = current_needbar["colors"]
        if colors:
            # Remove space from color names
            colors = [x.strip() for x in colors]

        # Handle the cases: len(local_data) > len(colors) or len(local_data) < len(colors)
        # We do the same for input color, with transpose the user could forget to change the color accordingly
        if not colors or len(colors) == 0:
            # Set default colors, if nothing is given
            colors = matplotlib.rcParams["axes.prop_cycle"].by_key()["color"]
        else:
            # extend given colors with default colors
            colors = colors + matplotlib.rcParams["axes.prop_cycle"].by_key()["color"]
        multi = math.ceil(len(local_data) / len(colors))
        if multi > 1:
            print(
                f"{error_id} warning: color schema is smaller than data, double coloring is occurring"
            )
        colors = colors * multi
        colors = colors[: len(local_data)]

        y_offset = [0.0 for _ in range(len(local_data_number[0]))]

        # 8. create figure
        bar_labels = []
        figure, axes = matplotlib.pyplot.subplots()
        for x in range(len(local_data_number)):
            if not current_needbar["horizontal"]:
                bar = axes.bar(
                    index[x],
                    local_data_number[x],
                    bottom=y_offset,
                    label=ylabels[x],
                    color=colors[x],
                )
            else:
                bar = axes.barh(
                    index[x],
                    local_data_number[x],
                    left=y_offset,
                    label=ylabels[x],
                    color=colors[x],
                )

            if current_needbar["stacked"]:
                # handle stacked bar
                y_offset = [i + j for i, j in zip(y_offset, local_data_number[x])]

            if current_needbar["show_sum"]:
                try:
                    bar_label = axes.bar_label(
                        bar, label_type="center"
                    )  # show label in the middel of each bar
                    bar_labels.append(bar_label)
                except (
                    AttributeError
                ):  # bar_label is not support in older matplotlib versions
                    current_needbar["show_sum"] = None
                    current_needbar["show_top_sum"] = None

            if current_needbar["show_top_sum"] and (
                not current_needbar["stacked"] or (x == len(local_data_number) - 1)
            ):
                # "show_top_sum" and ( not stacked or end of stack )
                try:
                    bar_label = axes.bar_label(bar)
                    bar_labels.append(bar_label)
                except (
                    AttributeError
                ):  # bar_label is not support in older matplotlib versions
                    current_needbar["show_sum"] = None
                    current_needbar["show_top_sum"] = None

        sum_rotation = current_needbar["sum_rotation"]
        if sum_rotation and (
            current_needbar["show_top_sum"] or current_needbar["show_sum"]
        ):
            sum_rotation = sum_rotation.strip()
            # Rotate the bar labels
            if sum_rotation.isdigit():
                matplotlib.pyplot.setp(bar_labels, rotation=int(sum_rotation))

        centers = [
            (i + j) / 2.0 for i, j in zip(index[0], index[len(local_data_number) - 1])
        ]
        if not current_needbar["horizontal"]:
            # We want to support even older version of matplotlib, which do not support axes.set_xticks(labels)
            axes.set_xticks(centers)
            axes.set_xticklabels(labels=xlabels)
        else:
            # We want to support even older version of matplotlib, which do not support axes.set_yticks(labels)
            axes.set_yticks(centers)
            axes.set_yticklabels(labels=xlabels)
            axes.invert_yaxis()  # labels read top-to-bottom

        xlabels_rotation = current_needbar["xlabels_rotation"]
        if xlabels_rotation:
            xlabels_rotation = xlabels_rotation.strip()
            # Rotate the tick labels
            if xlabels_rotation.isdigit():
                matplotlib.pyplot.setp(
                    axes.get_xticklabels(), rotation=int(xlabels_rotation)
                )

        ylabels_rotation = current_needbar["ylabels_rotation"]
        if ylabels_rotation:
            ylabels_rotation = ylabels_rotation.strip()
            # Rotate the tick labels
            if ylabels_rotation.isdigit():
                matplotlib.pyplot.setp(
                    axes.get_yticklabels(), rotation=int(ylabels_rotation)
                )

        if current_needbar["title"]:
            axes.set_title(current_needbar["title"].strip())

        if current_needbar["x_axis_title"]:
            axes.set_xlabel(current_needbar["x_axis_title"].strip())

        if current_needbar["y_axis_title"]:
            axes.set_ylabel(current_needbar["y_axis_title"].strip())

        if current_needbar["legend"]:
            axes.legend()

        # 9. final storage

        # We need to calculate an unique bar-image file name
        hash_value = hashlib.sha256(id.encode()).hexdigest()[:5]
        image_node = save_matplotlib_figure(
            app, figure, f"need_bar_{hash_value}", fromdocname
        )

        # Add lineno to node
        image_node.line = current_needbar["lineno"]

        # normally the title is more understandable for a person who needs alt
        if current_needbar["title"]:
            image_node["alt"] = current_needbar["title"].strip()

        node.replace_self(image_node)

        # 10. cleanup matplotlib
        # Reset the style configuration:
        matplotlib.rcParams = style_previous_to_script_execution

        # close the figure, to free consumed memory. Otherwise we will get:
        # RuntimeWarning from matplotlib: More than 20 figures have been opened.
        matplotlib.pyplot.close(figure)
