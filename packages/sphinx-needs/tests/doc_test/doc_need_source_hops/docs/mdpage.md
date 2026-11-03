---
myst:
  substitutions:
    key: value
---

# MD page

## MD sub

```{req} md need
:id: REQ_MDX

body line
```

:::{req} colon need
:id: REQ_MDCOLX

colon body
:::

```{include} frag/c.md
```

```{list2need}
:types: req, req

* (REQ_MDL1X) md list need
  * (REQ_MDL2X) nested md list need
```
