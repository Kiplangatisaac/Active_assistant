use std::fs::{self, File};
use std::io::{self, BufReader, BufWriter};
use std::path::{Path, PathBuf};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const CORRUPTED_PREFIX: &str = "events_encrypted.corrupted.";
const CORRUPTED_ARCHIVE_EXT: &str = ".db.zst";
const MAX_CORRUPTED_ARCHIVES: usize = 2;
const MAX_ARCHIVE_AGE: Duration = Duration::from_secs(14 * 24 * 60 * 60);

pub struct CorruptedArchiveManager;

impl CorruptedArchiveManager {
    /// Compress a corrupted database file into a zstd archive, then delete uncompressed original
    pub fn compress_and_archive(primary_db_path: &Path) -> io::Result<PathBuf> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let archive_path = primary_db_path.with_file_name(format!(
            "{}{}{}",
            CORRUPTED_PREFIX, now, CORRUPTED_ARCHIVE_EXT
        ));

        let source_file = File::open(primary_db_path)?;
        let mut reader = BufReader::new(source_file);

        let target_file = File::create(&archive_path)?;
        let writer = BufWriter::new(target_file);
        let mut encoder = zstd::stream::Encoder::new(writer, 3)?;

        io::copy(&mut reader, &mut encoder)?;
        encoder.finish()?;

        // Delete uncompressed source file
        fs::remove_file(primary_db_path)?;

        // Clean accompanying journal files
        let _ = fs::remove_file(primary_db_path.with_extension("db-wal"));
        let _ = fs::remove_file(primary_db_path.with_extension("db-shm"));

        println!(
            "[Forensics Compression] Created compressed dump: {}",
            archive_path.display()
        );
        Ok(archive_path)
    }

    /// Discover, sort, and prune old corrupted archives based on count and age limits
    pub fn prune_corrupted_archives(data_dir: &Path) -> io::Result<usize> {
        if !data_dir.exists() {
            return Ok(0);
        }

        let now_epoch = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();

        let mut archives: Vec<(PathBuf, u64)> = Vec::new();

        for entry in fs::read_dir(data_dir)? {
            let entry = entry?;
            let path = entry.path();

            if !path.is_file() {
                continue;
            }

            if let Some(name) = path.file_name().and_then(|n| n.to_str()) {
                if name.starts_with(CORRUPTED_PREFIX) && name.ends_with(CORRUPTED_ARCHIVE_EXT) {
                    let ts_part = &name[CORRUPTED_PREFIX.len()..name.len() - CORRUPTED_ARCHIVE_EXT.len()];
                    let timestamp = ts_part.parse::<u64>().unwrap_or_else(|_| {
                        entry
                            .metadata()
                            .and_then(|m| m.modified())
                            .ok()
                            .and_then(|t| t.duration_since(UNIX_EPOCH).ok())
                            .map(|d| d.as_secs())
                            .unwrap_or(0)
                    });
                    archives.push((path, timestamp));
                }
            }
        }

        archives.sort_by(|a, b| b.1.cmp(&a.1));

        let mut deleted_count = 0;

        for (index, (path, timestamp)) in archives.iter().enumerate() {
            let age_secs = now_epoch.saturating_sub(*timestamp);
            let exceeds_count = index >= MAX_CORRUPTED_ARCHIVES;
            let exceeds_age = age_secs >= MAX_ARCHIVE_AGE.as_secs();

            if exceeds_count || exceeds_age {
                match fs::remove_file(path) {
                    Ok(_) => {
                        println!(
                            "[Forensics Cleanup] Pruned old archive: {}",
                            path.display()
                        );
                        deleted_count += 1;
                    }
                    Err(e) => {
                        eprintln!(
                            "[Forensics Cleanup Error] Failed to delete {}: {e}",
                            path.display()
                        );
                    }
                }
            }
        }

        Ok(deleted_count)
    }
}