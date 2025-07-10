// demo_3.cpp

/**
 * @file varied_example.cpp
 * @brief Test file with varied rst formatting.
 */

 #include <iostream>

 // GLOBAL REQUIRE: Feature G - Configuration management
 // Description: Manage application configuration.

 /**
  * @brief Function with varied rst spacing.
  *
  *
  */
 void logErrors() {
   // ... implementation ...
 }

 /**
  * @brief Function with rst on same line. (NOT valid)
  *
  */
// [[ IMPL_displayUI, displayUI() func\, so that it displays UI]]
 void displayUI(){
     //...
 }

 /**
  * @brief function with rst with extra space.
  *
  * \rst
  * .. impl:: Feature J - Data backup
  *   :id: IMPL_6
  *
  *   Backup user data.
  * \endrst
  *
  * // TODO: Improve backup performance.
  * // [[ IMPL_backupData, back up data]]
  */
 void backupData(){
     //...
 }

 // [[IMPL_main_demo_3, main func in demo_3.cpp]]
 int main() {
   std::cout << "Starting demo_3..." << std::endl;
   logErrors();
   displayUI();
   backupData();
   std::cout << "Demo_3 finished." << std::endl;
   return 0;
 }
