// demo_1.cpp

/**
 * @file another_example.cpp
 * @brief Test file with nested rst blocks.
 */

 #include <iostream>

 /**
  * @brief Function with nested reST blocks.
  *
  * Include details on how to handle edge cases.
  *
  * Additional processing steps here.
  * [[IMPL_processAssemble, processAssemble function]]
  */
 void processAssemble(){
     //...
 }

 // [[IMPL_main_demo1, main function]]
 int main() {
   std::cout << "Starting demo_1..." << std::endl;
   processAssemble();
   std::cout << "Demo_1 finished." << std::endl;
   return 0;
 }
