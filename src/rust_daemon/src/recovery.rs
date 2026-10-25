use crate::corrupt_cleanup::CorruptedArchiveManager;
use crate::diagnostics::{DisasterRecoveryReport, FileMetadataReport};
use rusqlite::Connection;
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

const BACKUP_PREFIX: &str = "events_encrypted.bak.";
const BACKUP_EXTENSION: &str = ".db";

pub struct DisasterRecovery;

impl DisasterRecovery {
    pub fn extract_file_meta(path: &Path) -> Option<FileMetadataReport> {
        let meta = fs::metadata(path).ok()?;
        let modified = meta
            .modified()
            .ok()
            .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
            .map(|d| d.as_secs())
            .unwrap_or(0);

        Some(FileMetadataReport {
            file_name: path.file_name()?.to_string_lossy().to_string(),
            size_bytes: meta.len(),
            modified_epoch_secs: modified,
        })
    }

    pub fn list_backups_sorted(data_dir: &Path) -> std::io::Result<Vec<PathBuf>> {
        if !data_dir.exists() {
            return Ok(Vec::new());
        }

        let mut backups: Vec<(PathBuf, u64)> = Vec::new();

        for entry in fs::read_dir(data_dir)? {
            let entry = entry?;
            let path = entry.path();

            if !path.is_file() {
                continue;
            }

            if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                if name.starts_with(BACKUP_PREFIX) && name.ends_with(BACKUP_EXTENSION) {
                    let raw_timestamp = &file_name[BACKUP_PREFIX.len()..file_name.len() - BACKUP_EXTENSION.len()];
                    let timestamp = raw_timestamp.parse::<u64>().unwrap_or(0);
                    backups.push((path, timestamp));
                }
            }
        }

        backups.sort_by(|a, b| b.1.cmp(&a.1));
        Ok(backups.into_iter().map(|(p, _)| p).collect())
    }

    pub fn verify_snapshot_integrity(snapshot_path: &Path, key_hex: &str) -> bool {
        let conn = match Connection::open(snapshot_path) {
            Ok(c) => c,
            Err(_) => return false,
        };

        let pragma_key = format!("PRAGMA key = \"x'{}'\";", key_hex);
        if conn.execute_batch(&pragma_key).is_err() {
            return false;
        }

        conn.query_row("SELECT count(*) FROM sqlite_master;", [], |_| Ok(()))
            .is_ok()
    }

    pub fn auto_restore_with_diagnostics(
        data_dir: &Path,
        primary_db_path: &Path,
        key_hex: &str,
        original_error: &str,
    ) -> Result<(PathBuf, DisasterRecoveryReport), Box<dyn std::error::Error>> {
        let start_time = Instant::now();

        let corrupted_file_meta = Self::extract_file_meta(primary_db_path);

        let backups = Self::list_backups_sorted(data_dir)?;
        let mut valid_backup: Option<PathBuf> = None;

        for candidate in backups {
            if Self::verify_snapshot_integrity(&candidate, key_hex) {
                valid_backup = Some(candidate);
                break;
            }
        }

        let chosen_snapshot = valid_backup
            .ok_or("No backups passed cryptographic integrity verification.")?;
        let snapshot_meta = Self::extract_file_meta(&chosen_snapshot)
            .ok_or("Failed to read restored snapshot metadata")?;

        let mut archived_target = None;
        if primary_db_path.exists() {
            let compressed_path = CorruptedArchiveManager::compress_and_archive(primary_db_path)?;
            archived_target = Some(compressed_path.to_string_lossy().to_string());
        }

        fs::copy(&chosen_snapshot, primary_db_path)?;
        let _ = CorruptedArchiveManager::prune_corrupted_archives(data_dir);

        let report = DisasterRecoveryReport {
            reason: "Database cryptographic validation failed on boot".to_string(),
            raw_error: original_error.to_string(),
            corrupted_file: corrupted_file_meta,
            restored_snapshot: snapshot_meta,
            archived_to: archived_target,
            recovery_duration_ms: start_time.elapsed().as_millis() as u64,
        };

        Ok((chosen_snapshot, report))
    }
}