use wasm_bindgen::prelude::*;
use tree_sitter::{Node, Parser};

#[wasm_bindgen]
pub struct WasmAstValidator {
    parser: Parser,
}

#[wasm_bindgen]
impl WasmAstValidator {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Result<WasmAstValidator, JsError> {
        let mut parser = Parser::new();
        parser
            .set_language(&tree_sitter_rust::LANGUAGE.into())
            .map_err(|e| JsError::new(&format!("Grammar initialization failed: {e}")))?;

        Ok(WasmAstValidator { parser })
    }

    /// Validates and truncates candidate completion so it cuts off at a clean AST boundary.
    /// Returns None if no valid syntax segment exists.
    #[wasm_bindgen]
    pub fn truncate_completion(
        &mut self,
        prefix: &str,
        candidate: &str,
        suffix: &str,
    ) -> Option<String> {
        if candidate.trim().is_empty() {
            return None;
        }

        let prefix_bytes = prefix.as_bytes().len();
        let candidate_bytes = candidate.as_bytes().len();

        let full_text = format!("{}{}{}", prefix, candidate, suffix);
        let tree = self.parser.parse(&full_text, None)?;
        let root = tree.root_node();

        let completion_start = prefix_bytes;
        let completion_end = prefix_bytes + candidate_bytes;

        if Self::range_has_errors(root, completion_start, completion_end) {
            if let Some(clean_end) = Self::find_clean_boundary(root, completion_start, completion_end) {
                if clean_end > completion_start {
                    let valid_slice = &full_text[completion_start..clean_end];
                    return Some(valid_slice.to_string());
                }
            }
            return None;
        }

        Some(candidate.to_string())
    }

    fn range_has_errors(node: Node, start: usize, end: usize) -> bool {
        if node.is_error() || node.is_missing() {
            let n_start = node.start_byte();
            let n_end = node.end_byte();
            if !(n_end <= start || n_start >= end) {
                return true;
            }
        }

        let mut cursor = node.walk();
        for child in node.children(&mut cursor) {
            if child.end_byte() <= start {
                continue;
            }
            if child.start_byte() >= end {
                break;
            }
            if Self::range_has_errors(child, start, end) {
                return true;
            }
        }

        false
    }

    fn find_clean_boundary(node: Node, start: usize, end: usize) -> Option<usize> {
        let mut best_boundary: Option<usize> = None;
        let mut cursor = node.walk();

        for child in node.children(&mut cursor) {
            let c_start = child.start_byte();
            let c_end = child.end_byte();

            if c_end <= start {
                continue;
            }
            if c_start >= end {
                break;
            }

            if !child.is_error() && !child.has_error() && !child.is_missing() {
                if c_start >= start && c_end <= end {
                    best_boundary = Some(c_end);
                }
            }

            if let Some(child_boundary) = Self::find_clean_boundary(child, start, end) {
                best_boundary = Some(child_boundary);
            }
        }

        best_boundary
    }
}