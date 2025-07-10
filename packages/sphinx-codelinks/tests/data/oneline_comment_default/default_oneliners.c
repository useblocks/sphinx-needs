// @Function Foo, IMPL_1
void foo() {}

// @Function Bar, IMPL_2
void bar() {}

// @Function Baz\, as I want it, IMPL_3
void baz() {}

// @Function Bar\, , IMPL_4, impl, [SPEC_1, SPEC_2]
void bar() {}

/*
* Multiple lines comment
*
*
* @Function Bar, , IMPL_4, impl, [SPEC_1, SPEC_2]
*/
void bar() {}
