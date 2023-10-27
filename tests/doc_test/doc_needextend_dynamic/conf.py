extensions = ["sphinx_needs"]
needs_build_json = True


def get_matching_need_ids(app, need, needs, id_prefix=""):
    filtered_needs = []
    for need_id, _ in needs.items():
        if id_prefix and need_id.startswith(id_prefix):
            filtered_needs.append(need_id)
    return filtered_needs


needs_functions = [get_matching_need_ids]
