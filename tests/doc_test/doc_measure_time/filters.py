def own_filter_code(needs, results, **kwargs):
    for need in needs:
        if need["status"] == "closed":
            results.append(need)
