use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FileMetadataReport {
    pub file_name: String,
    pub size_bytes: u64,
    pub modified_epoch_secs: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisasterRecoveryReport {
    pub reason: String,
    pub raw_error: String,
    pub corrupted_file: Option<FileMetadataReport>,
    pub restored_snapshot: FileMetadataReport,
    pub archived_to: Option<String>,
    pub recovery_duration_ms: u64,
}