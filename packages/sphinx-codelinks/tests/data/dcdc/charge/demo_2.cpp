// demo_2.cpp

/**
 * @file another_example.cpp
 * @brief Test file with nested rst blocks.
 */

 #include <iostream>

 /**
  * @brief Function with nested reST blocks.
  *
  *
  * Include details on how to handle edge cases.
  *
  * Additional processing steps here.
  * [[IMPL_filterData, filterData func, impl]]
  */
 void filterData() {
   // ... implementation ...
 }

 /**
  * @brief Function with multiple rst blocks.
  *
  * Some code here.
  *
  *  Feature F - Data visualization
  * [[IMPL_processAggregate, processAggregate]]
  */
 void processAggregate(){
     //...
 }

  /**
  * @brief Function with a rst blocks.
  * .. impl:: Feature G - Data loss prevention
  *
  * Some description here.
  * [[ IMPL_main_demo2, main func in demo_2]]
  */
 int main() {
   std::cout << "Starting demo_2..." << std::endl;
   filterData();
   processAggregate();
   std::cout << "Demo_2 finished." << std::endl;
   return 0;
 }
