// [[IMPL_1, Function Foo]]
void foo() {}

// [[IMPL_2, Function Bar, impl, [], closed]]
void bar() {}

// [[IMPL_3, Function Baz\, as I want it, impl, [], closed]]
void baz() {}

// [[IMPL_5, Function Bar, impl, [SPEC_1, SPEC_2], open]]
void bar() {}

// [[IMPL_6, Function Bar, impl, [SPEC_1, SPEC_2], [open]]]
// valid because "[open]" is parsed into field status
void foo() {}

// [[IMPL_7, Function has a, in the title]]
// title has a non-escaped split char ','
// type will be set to 'in the title' (will lead to a SN error)
void baz() {}

// [[IMPL_8, [Title starts with a bracket], impl]]
// valid because title is of type string, it will be parsed to
// '[Title starts with a bracket]'
void baz() {}

// [[IMPL_9, Function Baz, impl, [SPEC_1, SPEC_2[text], SPEC_3], open]]
// valid because the 2nd link item is 'SPEC_2]'
void baz() {}
