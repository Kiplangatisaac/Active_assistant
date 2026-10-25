use crate::corrupt_cleanup::CorruptedArchiveManager;
use crate::crypto;
use crate::db::EncryptedDatabaseStore;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const ROTATION_INTERVAL_SECS: u64 = 30 * 24 * 60 * 60;
const CHECK_FREQUENCY: Duration = Duration::from_secs(6 * 3600);

pub fn start_maintenance_scheduler(db: EncryptedDatabaseStore) {
    tokio::spawn(async move {
        let mut ticker = tokio::time::interval(CHECK_FREQUENCY);

        loop {
            ticker.tick().await;

            let db_clone = db.clone();
            tokio::task::spawn_blocking(move || {
                let last_rotation = db_clone.get_last_rotation_timestamp().unwrap_or(0);
                let now = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();

                if (now.saturating_sub(last_rotation)) >= ROTATION_INTERVAL_SECS {
                    println!("[Scheduler] 30-day key rotation due. Performing safe rotation...");
                    if let Ok(current_key) = crypto::get_or_create_db_key() {
                        let new_key = crypto::generate_secure_hex_key();

                        if db_clone.safe_rotate_encryption_key(&current_key, &new_key).is_ok() {
                            let _ = db_clone.update_last_rotation_timestamp(now);
                            println!("[Scheduler] Key rotation completed successfully.");
                        }
                    }
                }

                if let Ok(proj_dirs) = directories::ProjectDirs::from("com", "ActiveAssistant", "Daemon") {
                    let data_dir = proj_dirs.data_local_dir();
                    let _ = CorruptedArchiveManager::prune_corrupted_archives(data_dir);
                }
            }).await.ok();
        }
    });
}