def tr_link(app, need, needs, test_option, target_option, *args, **kwargs):
    # Fields default to None on needs that do not set them (e.g. non-test needs)
    if not need.get(test_option):
        return ""

    # Allow for multiple values in option
    test_opt_values = need[test_option].split(",")

    links = []
    for need_target in needs.values():
        if target_option not in need_target:
            continue
        for test_opt_raw in test_opt_values:
            test_opt = test_opt_raw.strip()
            if (
                test_opt == need_target[target_option]
                and test_opt is not None
                and len(test_opt) > 0
            ):
                links.append(need_target["id"])

    return links
