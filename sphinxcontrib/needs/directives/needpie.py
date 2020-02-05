import os
import re
import sphinx
import sys
import urllib

from docutils import nodes
from pkg_resources import parse_version

import matplotlib

from sphinxcontrib.needs.filter_common import FilterBase, filter_needs

if not os.environ.get('DISPLAY'):
    matplotlib.use('Agg')
import matplotlib.pyplot
import hashlib
from docutils.parsers.rst import directives

try:
    from sphinx.errors import NoUri  # Sphinx 3.0
except ImportError:
    from sphinx.environment import NoUri  # Sphinx < 3.0


sphinx_version = sphinx.__version__
if parse_version(sphinx_version) >= parse_version("1.6"):
    from sphinx.util import logging
else:
    import logging
logger = logging.getLogger(__name__)

if sys.version_info.major < 3:
    urlParse = urllib.quote_plus
else:
    urlParse = urllib.parse.quote_plus


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
        'legend': directives.unchanged,
        'explode': directives.unchanged_required,
        'labels': directives.unchanged_required,
        'style': directives.unchanged_required,
        'colors': directives.unchanged_required,
        'text_color': directives.unchanged_required,
        'shadow': directives.flag
    }

    def run(self):
        env = self.state.document.settings.env
        if not hasattr(env, 'need_all_needpie'):
            env.need_all_needpie = {}

        # be sure, global var is available. If not, create it
        if not hasattr(env, 'needs_all_needs'):
            env.needs_all_needs = {}

        id = env.new_serialno('needpie')
        targetid = "needpie-{docname}-{id}".format(
            docname=env.docname,
            id=id)
        targetnode = nodes.target('', '', ids=[targetid])

        content = self.content
        title = self.arguments[0] if self.arguments else ""
        text_color = self.options.get('text_color', None)
        style = self.options.get('style', None)
        legend = self.options.get('legend', None)

        explode = self.options.get('explode', None)
        if explode is not None and len(explode) > 0:
            explode = explode.split(',')
            explode = [float(ex) for ex in explode]  # Transform all values to floats

        labels = self.options.get('labels', None)
        if labels is not None and len(labels) > 0:
            labels = labels.split(',')

        colors = self.options.get('colors', None)
        if colors is not None and len(colors) > 0:
            colors = colors.split(',')

        shadow = True if 'shadow' in self.options else False

        # Add the need and all needed information
        env.need_all_needpie[targetid] = {
            'docname': env.docname,
            'lineno': self.lineno,
            'target_node': targetnode,
            'env': env,
            'title': title,
            'content': content,
            'legend': legend,
            'explode': explode,
            'style': style,
            'labels': labels,
            'colors': colors,
            'shadow': shadow,
            'text_color': text_color,
        }

        return [targetnode] + [Needpie('')]


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
            for att in ('ids', 'names', 'classes', 'dupnames'):
                node[att] = []
            node.replace_self([])
            continue


        id = node.attributes["ids"][0]
        current_needpie = env.need_all_needpie[id]

        # Set matplotlib style
        if current_needpie['style'] is not None:
            matplotlib.style.use(current_needpie['style'])
        else:
            matplotlib.style.use('default')

        content = current_needpie['content']
        sizes = []
        for line in content:
            if line.isdigit():
                sizes.append(float(line))
            else:
                result = len(filter_needs(app.env.needs_all_needs.values(), line))
                sizes.append(result)

        labels = current_needpie['labels']
        if labels is None:
            labels = [''] * len(sizes)

        colors = current_needpie['colors']
        if colors is None:
            # Set default colors, if nothing is given
            colors = matplotlib.rcParams['axes.prop_cycle'].by_key()['color']
        else:
            # Remove space from color names
            colors = [x.strip() for x in colors]

        explode = current_needpie['explode']
        if explode is None:
            explode = [0] * len(labels)

        shadow = current_needpie['shadow']
        text_color = current_needpie['text_color']

        fig, axes = matplotlib.pyplot.subplots(figsize=(8, 4), subplot_kw=dict(aspect="equal"))

        pie_kwargs = {
            'labels': labels,
            'startangle': 90,
            'explode': explode,
            'autopct': lambda pct: func(pct, sizes),
            'shadow': shadow,
            'colors': colors,
        }

        if text_color is not None:
            pie_kwargs['textprops'] = dict(color=text_color)

        wedges, texts, autotexts = axes.pie(sizes, **pie_kwargs)

        if text_color is not None:
            for autotext in autotexts:
                autotext.set_color(text_color)
        axes.axis('equal')

        # Legend preparation
        if current_needpie['legend'] is not None:
            axes.legend(wedges, labels,
                        title=str(current_needpie['legend']),
                        loc="center left",
                        bbox_to_anchor=(0.8, 0, 0.5, 1))

        matplotlib.pyplot.setp(autotexts, size=8, weight="bold")

        if current_needpie['title'] is not None and len(current_needpie['title']) > 0:
            axes.set_title(current_needpie['title'])

        # Final storage
        image_folder = os.path.join(env.app.srcdir, '_images')
        if not os.path.exists(image_folder):
            os.mkdir(image_folder)
        # We need to calculate an unique pie-image file name
        hash_value = hashlib.sha256(id.encode()).hexdigest()[:5]
        rel_file_path = os.path.join('_images', 'need_pie_{}.png'.format(hash_value))
        if rel_file_path not in env.images:
            fig.savefig(os.path.join(env.app.srcdir, rel_file_path), format='png')
            env.images[rel_file_path] = ['_images', os.path.split(rel_file_path)[-1]]

        image_node = nodes.image()
        image_node['uri'] = rel_file_path
        image_node['candidates'] = '*'  # look at uri value for source path, relative to the srcdir folder
        node.replace_self(image_node)


def func(pct, allvals):
    absolute = int(pct / 100. * sum(allvals))
    return "{:.1f}%\n({:d})".format(pct, absolute)
