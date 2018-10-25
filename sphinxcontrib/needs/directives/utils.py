from docutils import nodes


def no_needs_found_paragraph():
    nothing_found = "No needs passed the filters"
    para = nodes.paragraph()
    nothing_found_node = nodes.Text(nothing_found, nothing_found)
    para += nothing_found_node
    return para


def used_filter_paragraph(current_needfilter):
    para = nodes.paragraph()
    filter_text = "Used filter:"
    filter_text += " status(%s)" % " OR ".join(current_needfilter["status"]) if len(
        current_needfilter["status"]) > 0 else ""
    if len(current_needfilter["status"]) > 0 and len(current_needfilter["tags"]) > 0:
        filter_text += " AND "
    filter_text += " tags(%s)" % " OR ".join(current_needfilter["tags"]) if len(
        current_needfilter["tags"]) > 0 else ""
    if (len(current_needfilter["status"]) > 0 or len(current_needfilter["tags"]) > 0) and len(
            current_needfilter["types"]) > 0:
        filter_text += " AND "
    filter_text += " types(%s)" % " OR ".join(current_needfilter["types"]) if len(
        current_needfilter["types"]) > 0 else ""

    filter_node = nodes.emphasis(filter_text, filter_text)
    para += filter_node
    return para
