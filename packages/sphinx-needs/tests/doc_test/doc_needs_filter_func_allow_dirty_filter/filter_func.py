def my_own_filter(needs, results, **kwargs):
    needs_dict = {x["id"]: x for x in needs}
    curr_need_id = kwargs["arg1"]
    link_type = kwargs["arg2"]

    for link_id in needs_dict[curr_need_id][link_type]:
        if needs_dict[curr_need_id]["ti"] == "1":
            needs_dict[link_id]["tcl"] = "10"
        elif needs_dict[curr_need_id]["ti"] == "3":
            needs_dict[link_id]["tcl"] = "30"
        else:
            needs_dict[link_id]["tcl"] = "unknown"

        results.append(needs_dict[link_id])
