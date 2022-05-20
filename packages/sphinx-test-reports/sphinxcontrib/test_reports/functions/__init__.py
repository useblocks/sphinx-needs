def tr_link(app, need, needs, test_option, target_option, *args, **kwargs):
    if test_option not in need:
        return ""
    test_opt = need[test_option]

    links = []
    for need_target in needs.values():
        if target_option not in need_target:
            continue

        if (
            test_opt == need_target[target_option] and test_opt is not None and len(test_opt) > 0  # fmt: skip
        ):
            links.append(need_target["id"])

    return links
