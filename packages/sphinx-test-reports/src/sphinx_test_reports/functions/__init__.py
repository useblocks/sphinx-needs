def tr_link(app, need, needs, test_option, target_option, *args, **kwargs):
    # Guard on the VALUE, not the key: the test fields are registered on every need, so
    # the key is present on a need that is not a test-case too, with the value `None`.
    # No links is the empty LIST: an empty string is read as one link to the id `""`,
    # which sphinx-needs reports as a dead outgoing link.
    test_value = need.get(test_option)
    if not test_value:
        return []

    # Allow for multiple values in option
    test_opt_values = test_value.split(",")

    links = []
    for need_target in needs.values():
        # the same on the target side: a need whose target option is unset is no target
        target_value = need_target.get(target_option)
        if not target_value:
            continue
        for test_opt_raw in test_opt_values:
            test_opt = test_opt_raw.strip()
            if test_opt == target_value and len(test_opt) > 0:
                links.append(need_target["id"])

    return links
