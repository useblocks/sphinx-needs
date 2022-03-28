import copy
import os

import matplotlib
import numpy as np
from docutils import nodes

from sphinxcontrib.needs.filter_common import (
    FilterBase,
    filter_needs,
    prepare_need_list,
)

if not os.environ.get("DISPLAY"):
    matplotlib.use("Agg")
import hashlib

import matplotlib.pyplot
from docutils.parsers.rst import directives

from sphinxcontrib.needs.logging import get_logger
from sphinxcontrib.needs.utils import check_and_get_external_filter_func

logger = get_logger(__name__)


class Needpie(nodes.General, nodes.Element):
    pass


class NeedpieDirective(FilterBase):
    """
    Directive to plot diagrams with the help of matplotlib

    .. versionadded: 0.4.4
    """

    has_content = True

    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = True

    option_spec = {
        "legend": directives.flag,
        "explode": directives.unchanged_required,
        "labels": directives.unchanged_required,
        "style": directives.unchanged_required,
        "colors": directives.unchanged_required,
        "text_color": directives.unchanged_required,
        "shadow": directives.flag,
        "filter-func": FilterBase.base_option_spec["filter-func"],
    }

    # Update the options_spec only with value filter-func defined in the FilterBase class

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, "need_all_needpie"):
            env.need_all_needpie = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, "needs_all_needs"):
            env.needs_all_needs = {}

        id = env.new_serialno("needpie")
        targetid = f"needpie-{env.docname}-{id}"
        targetnode = nodes.target("", "", ids=[targetid])

        content = self.content
        title = self.arguments[0] if self.arguments else ""
        text_color = self.options.get("text_color", None)
        style = self.options.get("style", None)
        legend = "legend" in self.options

        explode = self.options.get("explode", None)
        if explode:
            explode = explode.split(",")
            explode = [float(ex) for ex in explode]  # Transform all values to floats

        labels = self.options.get("labels", None)
        if labels:
            labels = labels.split(",")

        colors = self.options.get("colors", None)
        if colors:
            colors = colors.split(",")

        shadow = "shadow" in self.options

        # Stores infos for needpie
        env.need_all_needpie[targetid] = {
            "docname": env.docname,
            "lineno": self.lineno,
            "target_node": targetnode,
            "env": env,
            "title": title,
            "content": content,
            "legend": legend,
            "explode": explode,
            "style": style,
            "labels": labels,
            "colors": colors,
            "shadow": shadow,
            "text_color": text_color,
        }
        # update filter-func with needed information defined in FilterBase class
        env.need_all_needpie[targetid]["filter_func"] = self.collect_filter_attributes()["filter_func"]

        return [targetnode] + [Needpie("")]


def process_needpie(app, doctree, fromdocname):
    env = app.builder.env

    # NEEDFLOW
    for node in doctree.traverse(Needpie):
        if not app.config.needs_include_needs:
            # Ok, this is really dirty.
            # If we replace a node, docutils checks, if it will not lose any attributes.
            # But this is here the case, because we are using the attribute "ids" of a node.
            # However, I do not understand, why losing an attribute is such a big deal, so we delete everything
            # before docutils claims about it.
            for att in ("ids", "names", "classes", "dupnames"):
                node[att] = []
            node.replace_self([])
            continue

        id = node.attributes["ids"][0]
        current_needpie = env.need_all_needpie[id]

        # Set matplotlib style
        style_previous_to_script_execution = matplotlib.rcParams
        if current_needpie["style"]:
            matplotlib.style.use(current_needpie["style"])
        else:
            matplotlib.style.use("default")

        content = current_needpie["content"]

        sizes = []
        need_list = list(prepare_need_list(app.env.needs_all_needs.values()))  # adds parts to need_list
        if content and not current_needpie["filter_func"]:
            for line in content:
                if line.isdigit():
                    sizes.append(float(line))
                else:
                    result = len(filter_needs(app, need_list, line))
                    sizes.append(result)
        elif current_needpie["filter_func"] and not content:
            try:
                # check and get filter_func
                filter_func, filter_args = check_and_get_external_filter_func(current_needpie)
                # execute filter_func code
                # Provides only a copy of needs to avoid data manipulations.
                context = {
                    "needs": copy.deepcopy(need_list),
                    "results": [],
                }
                args = []
                if filter_args:
                    args = filter_args.split(",")
                for index, arg in enumerate(args):
                    # All rgs are strings, but we must transform them to requested type, e.g. 1 -> int, "1" -> str
                    context[f"arg{index + 1}"] = arg

                if filter_func:
                    filter_func(**context)
                sizes = context["results"]
                # check items in sizes
                if not isinstance(sizes, list):
                    logger.error(
                        f"The returned values from the given filter_func {filter_func.__name__} is not valid."
                        " It must be a list."
                    )
                for item in sizes:
                    if not isinstance(item, int) and not isinstance(item, float):
                        logger.error(
                            f"The returned values from the given filter_func {filter_func.__name__} is not valid. "
                            "It must be a list with items of type int/float."
                        )
            except Exception as e:
                raise e
        elif current_needpie["filter_func"] and content:
            logger.error("filter_func and content can't be used at the same time for needpie.")
        else:
            logger.error("Both filter_func and content are not used for needpie.")

        labels = current_needpie["labels"]
        if labels is None:
            labels = [""] * len(sizes)

        colors = current_needpie["colors"]
        if colors is None:
            # Set default colors, if nothing is given
            colors = matplotlib.rcParams["axes.prop_cycle"].by_key()["color"]
        else:
            # Remove space from color names
            colors = [x.strip() for x in colors]

        explode = current_needpie["explode"]
        if explode is None:
            explode = [0] * len(labels)

        shadow = current_needpie["shadow"]
        text_color = current_needpie["text_color"]

        fig, axes = matplotlib.pyplot.subplots(figsize=(8, 4), subplot_kw={"aspect": "equal"})

        pie_kwargs = {
            "labels": labels,
            "startangle": 90,
            "explode": explode,
            "autopct": lambda pct: label_calc(pct, sizes),
            "shadow": shadow,
            "colors": colors,
        }

        if text_color:
            pie_kwargs["textprops"] = {"color": text_color}

        wedges, _texts, autotexts = axes.pie(sizes, normalize=np.asarray(sizes, np.float32).sum() >= 1, **pie_kwargs)

        if text_color:
            for autotext in autotexts:
                autotext.set_color(text_color)
        axes.axis("equal")

        # Legend preparation
        if current_needpie["legend"]:
            axes.legend(
                wedges, labels, title=str(current_needpie["legend"]), loc="center left", bbox_to_anchor=(0.8, 0, 0.5, 1)
            )

        matplotlib.pyplot.setp(autotexts, size=8, weight="bold")

        if current_needpie["title"]:
            axes.set_title(current_needpie["title"])

        # Final storage
        image_folder = os.path.join(env.app.srcdir, "_images")
        if not os.path.exists(image_folder):
            os.mkdir(image_folder)
        # We need to calculate an unique pie-image file name
        hash_value = hashlib.sha256(id.encode()).hexdigest()[:5]
        rel_file_path = os.path.join("_images", f"need_pie_{hash_value}.png")
        if rel_file_path not in env.images:
            fig.savefig(os.path.join(env.app.srcdir, rel_file_path), format="png")
            # env.images[rel_file_path] = ["_images", os.path.split(rel_file_path)[-1]]
            env.images.add_file(fromdocname, rel_file_path)

        image_node = nodes.image()
        image_node["uri"] = rel_file_path

        # look at uri value for source path, relative to the srcdir folder
        image_node["candidates"] = {"*": rel_file_path}

        # Add lineno to node
        image_node.line = current_needpie["lineno"]

        node.replace_self(image_node)

        # Cleanup matplotlib
        # Reset the style configuration:
        matplotlib.rcParams = style_previous_to_script_execution

        # Close the figure, to free consumed memory.
        # Otherwise we will get: RuntimeWarning from matplotlib:
        matplotlib.pyplot.close(fig)


def label_calc(pct, allvals):
    absolute = int(round(pct / 100.0 * sum(allvals)))
    return f"{pct:.1f}%\n({absolute:d})"
