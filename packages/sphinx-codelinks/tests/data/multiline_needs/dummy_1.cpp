 #include <iostream>

/**
 * @need impl: implement dummy function 1
 * :id: IMPL_71
 *
 * The function does *nothing* yet.
 * @endneed
 */
 void dummy_func1(){
     //...
 }

 // @need[md] impl: implement main function
 // :id: IMPL_72
 //
 // Calls **dummy_func1**.
 // @endneed
int main() {
   std::cout << "Starting demo_1..." << std::endl;
   dummy_func1();
   std::cout << "Demo_1 finished." << std::endl;
   return 0;
 }
