 #include <iostream>

// @need-ids: NEED_001, NEED_002, NEED_003, NEED_004
 void dummy_func1(){
     //...
 }

 // @need-ids: NEED_003
int main() {
   std::cout << "Starting demo_1..." << std::endl;
   dummy_func1();
   std::cout << "Demo_1 finished." << std::endl;
   return 0;
 }
