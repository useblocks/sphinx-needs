 #include <iostream>

// @need-ids: need_001, need_002, need_003, need_004
 void dummy_func1(){
     //...
 }

 // @need-ids: need_003
int main() {
   std::cout << "Starting demo_1..." << std::endl;
   dummy_func1();
   std::cout << "Demo_1 finished." << std::endl;
   return 0;
 }
