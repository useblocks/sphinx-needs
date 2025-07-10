
#include <iostream>

// [[IMPL_singleLineExample, singleLineExample func, impl, [IMPL_main_demo_3, IMPL_main_demo2]]]
void singleLineExample()
{
    std::cout << "Single-line comment example" << std::endl;
}

/*
 *
 * This is a multi-line comment example.
 * It spans multiple lines and contains detailed information.
 * [[IMPL_multiLineExample, multiLineExample func, impl, [IMPL_main_demo_3, IMPL_main_demo1]]]
 */
void multiLineExample()
{
    std::cout << "Multi-line comment example" << std::endl;
}

// [[IMPL_14, title 13, impl, 13[\[SPEC\,_1\]], open, low, high]]
// invalid because the too many fields
void baz() {}

// one-line comment style: [[IMPL_main_supercharge, main func in supercharge.cpp, impl, [IMPL_main_demo_3, IMPL_main_demo1, IMPL_main_demo2]]]
int main()
{
    singleLineExample();
    multiLineExample();
    return 0;
}
