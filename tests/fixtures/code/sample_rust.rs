// Sample Rust file for testing code-aware chunking.
//
// Contains structs, impl blocks, functions, and traits.

use std::collections::HashMap;
use std::path::PathBuf;

/// Configuration for the data processor.
#[derive(Debug, Clone)]
pub struct Config {
    pub source: String,
    pub max_records: usize,
    pub output_path: PathBuf,
}

impl Config {
    /// Create a new configuration with defaults.
    pub fn new(source: &str) -> Self {
        Config {
            source: source.to_string(),
            max_records: 1000,
            output_path: PathBuf::from("output"),
        }
    }

    /// Set the maximum number of records.
    pub fn with_max_records(mut self, max: usize) -> Self {
        self.max_records = max;
        self
    }
}

/// A record in the data store.
#[derive(Debug, Clone)]
pub struct Record {
    pub id: String,
    pub name: String,
    pub value: f64,
}

impl Record {
    /// Validate the record.
    pub fn is_valid(&self) -> bool {
        !self.id.is_empty() && !self.name.is_empty() && self.value.is_finite()
    }

    /// Transform the record for output.
    pub fn normalize(&self) -> Record {
        Record {
            id: self.id.clone(),
            name: self.name.trim().to_lowercase(),
            value: (self.value * 100.0).round() / 100.0,
        }
    }
}

/// Process a batch of records.
pub fn process_batch(records: &[Record], config: &Config) -> Vec<Record> {
    records
        .iter()
        .take(config.max_records)
        .filter(|r| r.is_valid())
        .map(|r| r.normalize())
        .collect()
}

/// Merge two vectors of records by ID.
pub fn merge_records(a: &[Record], b: &[Record]) -> Vec<Record> {
    let mut seen: HashMap<String, bool> = HashMap::new();
    let mut merged: Vec<Record> = Vec::new();

    for record in a.iter().chain(b.iter()) {
        if !seen.contains_key(&record.id) {
            seen.insert(record.id.clone(), true);
            merged.push(record.clone());
        }
    }

    merged
}
