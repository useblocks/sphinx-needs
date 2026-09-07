from docutils import nodes


class Need(nodes.General, nodes.Element):
    """
    Node for containing a complete need.
    Node structure:

    - need
      - headline container
      - meta container ()
      - content container

    As the content container gets rendered RST input, this must already be created during
    node handling and can not be done later during event handling.
    Reason: nested_parse_with_titles() needs self.state, which is available only during node handling.

    headline and content container get added later during event handling (process_need_nodes()).
    """

    child_text_separator = "\n"
