#include "nonexistent_header.h"

// @Works Despite Errors, IMPL_DESPITE, impl, [REQ_RESILIENT]
void works_despite_errors() { undeclared_function(); }

// @After Broken Block, IMPL_AFTER_BROKEN, impl, [REQ_RESILIENT]
void after_broken_block() {}
