//! Rust-accelerated components for Simulor
//!
//! This crate provides performance-critical implementations in Rust
//! with Python bindings via PyO3.

use pyo3::prelude::*;

/// Python module definition
#[pymodule]
fn _simulor_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Version info
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    Ok(())
}
