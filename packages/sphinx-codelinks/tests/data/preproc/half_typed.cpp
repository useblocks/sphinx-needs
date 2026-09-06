#include <nonexistent.h>

// @Complete Function, IMPL_COMPLETE, impl, [REQ_OK]
void complete_function() { int x = 42; }

// @Half Typed Function, IMPL_HALF, impl, [REQ_PARTIAL]
void half_typed_function() {
    if (some_condition

// @After Half Typed, IMPL_AFTER, impl, [REQ_RECOVERS]
void after_half_typed() { int y = 1; }

// @Mid Declaration, IMPL_MID, impl, [REQ_MID]
int
