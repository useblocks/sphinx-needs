import json
import sys


def extract(input_file, output_file):
    with open(input_file) as in_file:
        input_data = json.load(in_file)

    data = []

    for bench in input_data["benchmarks"]:
        name = bench["name"].split("[")[0]
        if name == "test_basic_time":
            name = "Small, basic Sphinx-Needs project"
        elif name == "test_official_time":
            name = "Official Sphinx-Needs documentation (without services)"

        output = {
            "name": name,
            "unit": "s",
            "value": bench["stats"]["mean"],
            "extra": f"Commit: {input_data['commit_info']['id']}\nBranch: {input_data['commit_info']['branch']}\
\nTime: {input_data['commit_info']['time']}",
        }
        data.append(output)

    with open(output_file, "w") as out_file:
        json.dump(data, out_file, sort_keys=True, indent=4)


if "main" in __name__:
    extract(sys.argv[1], sys.argv[2])
