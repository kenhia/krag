// Malformed Rust file for testing graceful fallback.
// This file has intentional syntax errors.

pub fn valid_function() -> i32 {
    42
}

pub fn broken_function( -> i32 {
    // Missing parameter list
    let x = 
}

struct IncompleteStruct {
    name: String,
    // missing closing brace
