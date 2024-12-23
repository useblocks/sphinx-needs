def own_filter_code(needs, results):
    for need in needs:
        if need["type"] == "test":
            results.append(need)


def own_filter_code_args(needs, results, **kwargs):
    for need in needs:
        if need["status"] == kwargs["arg1"]:
            results.append(need)


def my_pie_filter_code(needs, results):
    cnt_x = 0
    cnt_y = 0
    for need in needs:
        if need["variant"] == "project_x":
            cnt_x += 1
        if need["variant"] == "project_y":
            cnt_y += 1
    results.append(cnt_x)
    results.append(cnt_y)


def my_pie_filter_code_args(needs, results, **kwargs):
    cnt_x = 0
    cnt_y = 0
    for need in needs:
        if need["status"] == kwargs["arg1"]:
            cnt_x += 1
        if need["status"] == kwargs["arg2"]:
            cnt_y += 1
    results.append(cnt_x)
    results.append(cnt_y)
