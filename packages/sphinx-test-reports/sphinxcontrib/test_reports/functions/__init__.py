def test_link(app, need, needs, test_option, target_option, *args, **kwargs):
    if test_option not in need:
        return ""
    test_opt = need[test_option]

    links = []
    for need in needs.values():
        if target_option not in need:
            continue
        if test_opt == need[target_option]:
            links.append(need['id'])

    return links
