def own_filter_code(needs, results):
    for need in needs:
        if need["type"] == "test":
            results.append(need)
