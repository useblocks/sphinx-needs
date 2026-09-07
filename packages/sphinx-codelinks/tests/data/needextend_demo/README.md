# Needextend Demo

Run the following from `packages/sphinx-codelinks`, in an environment with the `docs`
extra (`uv run --frozen --extra docs-codelinks --directory packages/sphinx-codelinks …`
from the repository root, or the `.venvs/docs-codelinks` environment `poe docs-codelinks`
creates):

```bash
rm -rf tests/data/needextend_demo/_build output/marked_content.json \
       tests/data/needextend_demo/needextend.rst
codelinks analyse tests/data/configs/minimum_config.toml
codelinks write rst output/marked_content.json \
    --outpath tests/data/needextend_demo/needextend.rst
sphinx-build -nW --keep-going -b html -T -c tests/data/needextend_demo \
    tests/data/needextend_demo tests/data/needextend_demo/_build/html
```

These four commands were an environment of the old repository's test runner, written out
here. They are a demonstration rather than a gate -- nothing in CI or the test suite runs
them -- so they did not become a poe task at the monorepo import.
