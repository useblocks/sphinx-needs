def own_filter_code(needs, results):
    for need in needs:
        if need["type"] == "test":
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
