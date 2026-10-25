use std::fs;
use std::path::{Path, PathBuf};

const MAX_RETAINED_BACKUPS: usize = 3;
const BACKUP_PREFIX: &str = "events_encrypted.bak.";
const BACKUP_EXTENSION: &str = ".db";

pub fn prune_old_backups(data_dir: &Path, max_retain: usize) -> std::io::Result<usize> {
    if !data_dir.exists() {
        return Ok(0);
    }

    let mut backups: Vec<(PathBuf, u64)> = Vec::new();

    for entry in fs::read_dir(data_dir)? {
        let entry = entry?;
        let path = entry.path();

        if !path.is_file() {
            continue;
        }

        if let Some(file_name) = path.file_name().and_then(|n| n.to_str()) {
            if file_name.starts_with(BACKUP_PREFIX) && file_name.ends_with(BACKUP_EXTENSION) {
                let raw_timestamp = &file_name[BACKUP_PREFIX.len()..file_name.len() - BACKUP_EXTENSION.len()];
                let timestamp = raw_timestamp.parse::<u64>().unwrap_or(0);
                backups.push((path, timestamp));
            }
        }
    }

    backups.sort_by(|a, b| b.1.cmp(&a.1));

    let mut deleted_count = 0;
    if backups.len() > max_retain {
        for (path_to_delete, _) in &backups[max_retain..] {
            if fs::remove_file(path_to_delete).is_ok() {
                println!("[Backup Retention] Pruned old snapshot: {}", path_to_delete.display());
                deleted_count += 1;
            }
        }
    }

    Ok(deleted_count)
}