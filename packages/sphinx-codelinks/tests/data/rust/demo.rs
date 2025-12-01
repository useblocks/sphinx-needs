// demo.rs

/// This is a doc comment for the main function
/// @Main function implementation, main_demo, impl, [REQ_001]
fn main() {
    println!("Hello from Rust!");
    process_data();
}

// @Data processing function, process_func, impl, [REQ_002]
fn process_data() {
    let data = vec![1, 2, 3];
    for item in data {
        println!("Processing: {}", item);
    }
}

/* Block comment with marker
   @User data structure, struct_def, impl, [REQ_003]
*/
struct User {
    name: String,
    age: u32,
}

impl User {
    // @User constructor method, new_user, impl, [REQ_004]
    fn new(name: String, age: u32) -> Self {
        User { name, age }
    }
}
