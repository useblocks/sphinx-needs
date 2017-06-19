from docutils import nodes


def row_col_maker(app, fromdocname, all_needs, need_info, need_key, make_ref=False, ref_lookup=False):
    """
    Creates and returns a column.

    :param app: current sphinx app
    :param fromdocname: current document
    :param all_needs: Dictionary of all need objects
    :param need_info: need_info object, which stores all related need data
    :param need_key: The key to access the needed data from need_info
    :param make_ref: If true, creates a reference for the given data in need_key
    :param ref_lookup: If true, it uses the data to lookup for a related need and uses its data to create the reference
    :return: column object (nodes.entry)
    """
    row_col = nodes.entry()
    para_col = nodes.paragraph()

    if need_info[need_key] is not None:
        if not isinstance(need_info[need_key], list):
            data = [need_info[need_key]]
        else:
            data = need_info[need_key]

        for index, datum in enumerate(data):
            text_col = nodes.Text(datum, datum)
            if make_ref or ref_lookup:
                try:
                    ref_col = nodes.reference("", "")
                    if not ref_lookup:
                        ref_col['refuri'] = app.builder.get_relative_uri(fromdocname, need_info['docname'])
                        ref_col['refuri'] += "#" + datum
                    else:
                        temp_need = all_needs[datum]
                        ref_col['refuri'] = app.builder.get_relative_uri(fromdocname, temp_need['docname'])
                        ref_col['refuri'] += "#" + temp_need["id"]

                except KeyError:
                    para_col += text_col
                else:
                    ref_col.append(text_col)
                    para_col += ref_col
            else:
                para_col += text_col

            if index + 1 < len(data):
                para_col += nodes.emphasis("; ", "; ")

        row_col += para_col
    return row_col


def status_sorter(a):
    """
    Helper function to sort string elements, which can be None, too.
    :param a: element, which gets sorted
    :return:
    """
    if not a["status"]:
        return ""
    return a["status"]


def rstjinja(app, docname, source):
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    # Make sure we're outputting HTML
    if app.builder.format != 'html':
        return
    src = source[0]
    rendered = app.builder.templates.render_string(
        src, app.config.html_context
    )
    source[0] = rendered