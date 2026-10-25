use crate::backup_retention;
use crate::diagnostics::DisasterRecoveryReport;
use crate::recovery::DisasterRecovery;
use directories::ProjectDirs;
use rusqlite::{backup::Backup, params, Connection};
use serde::{Deserialize, Serialize};
use std::fs;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Duration;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NotificationEvent {
    pub id: u64,
    pub event_type: String,
    pub action_key: String,
    pub timestamp_ms: u64,
}

pub struct InitOutcome {
    pub store: EncryptedDatabaseStore,
    pub recovery_report: Option<(PathBuf, DisasterRecoveryReport)>,
}

#[derive(Clone)]
pub struct EncryptedDatabaseStore {
    conn: Arc<Mutex<Connection>>,
}

impl EncryptedDatabaseStore {
    pub fn new(encryption_key: &str) -> Result<InitOutcome, Box<dyn std::error::Error>> {
        let proj_dirs = ProjectDirs::from("com", "ActiveAssistant", "Daemon")
            .ok_or("Failed to determine application storage directory")?;
        let data_dir = proj_dirs.data_local_dir();
        fs::create_dir_all(data_dir)?;

        let db_path = data_dir.join("events_encrypted.db");
        let mut recovery_report = None;

        let conn = match Self::try_open_and_validate(&db_path, encryption_key) {
            Ok(c) => c,
            Err(e) => {
                let err_string = e.to_string();
                let (restored_path, report) = DisasterRecovery::auto_restore_with_diagnostics(
                    data_dir,
                    &db_path,
                    encryption_key,
                    &err_string,
                )?;
                recovery_report = Some((restored_path, report));
                Self::try_open_and_validate(&db_path, encryption_key)?
            }
        };

        conn.execute_batch(
            "PRAGMA cipher_memory_security = ON;
             PRAGMA journal_mode = WAL;
             PRAGMA synchronous = NORMAL;
             CREATE TABLE IF NOT EXISTS sse_events (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 event_type TEXT NOT NULL,
                 action_key TEXT NOT NULL,
                 timestamp_ms INTEGER NOT NULL
             );
             CREATE TABLE IF NOT EXISTS db_metadata (
                 key TEXT PRIMARY KEY,
                 value TEXT NOT NULL
             );
             CREATE INDEX IF NOT EXISTS idx_events_id ON sse_events(id);"
        )?;

        let store = Self {
            conn: Arc::new(Mutex::new(conn)),
        };

        Ok(InitOutcome {
            store,
            recovery_report,
        })
    }

    fn try_open_and_validate(path: &Path, key: &str) -> Result<Connection, Box<dyn std::error::Error>> {
        let conn = Connection::open(path)?;
        let pragma_key = format!("PRAGMA key = \"x'{}'\";", key);
        conn.execute_batch(&pragma_key)?;
        conn.query_row("SELECT count(*) FROM sqlite_master;", [], |_| Ok(()))?;
        Ok(conn)
    }

    pub fn insert_event(&self, event_type: &str, action_key: &str, timestamp_ms: u64) -> Result<u64, rusqlite::Error> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO sse_events (event_type, action_key, timestamp_ms) VALUES (?1, ?2, ?3)",
            params![event_type, action_key, timestamp_ms],
        )?;

        let last_id = conn.last_insert_rowid() as u64;
        conn.execute(
            "DELETE FROM sse_events WHERE id NOT IN (
                 SELECT id FROM sse_events ORDER BY id DESC LIMIT 500
             )",
            [],
        )?;

        Ok(last_id)
    }

    pub fn get_events_after(&self, last_seen_id: u64) -> Result<Vec<NotificationEvent>, rusqlite::Error> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, event_type, action_key, timestamp_ms 
             FROM sse_events 
             WHERE id > ?1 
             ORDER BY id ASC"
        )?;

        let event_iter = stmt.query_map(params![last_seen_id], |row| {
            Ok(NotificationEvent {
                id: row.get(0)?,
                event_type: row.get(1)?,
                action_key: row.get(2)?,
                timestamp_ms: row.get(3)?,
            })
        })?;

        let mut results = Vec::new();
        for event in event_iter {
            results.push(event?);
        }

        Ok(results)
    }

    pub fn create_backup(&self, current_key_hex: &str) -> Result<PathBuf, Box<dyn std::error::Error>> {
        let source_conn = self.conn.lock().unwrap();
        let db_path = self.get_db_path()?;
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)?
            .as_secs();
        let backup_path = db_path.with_extension(format!("bak.{}.db", timestamp));

        let mut dest_conn = Connection::open(&backup_path)?;
        let pragma_key = format!("PRAGMA key = \"x'{}'\";", current_key_hex);
        dest_conn.execute_batch(&pragma_key)?;

        {
            let backup = Backup::new(&source_conn, &mut dest_conn)?;
            backup.run_to_completion(100, Duration::from_millis(10), None)?;
        }

        println!("[Backup] Verified snapshot saved to: {}", backup_path.display());
        Ok(backup_path)
    }

    pub fn safe_rotate_encryption_key(
        &self,
        current_key_hex: &str,
        new_key_hex: &str,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let backup_path = self.create_backup(current_key_hex)?;

        let rotation_result = (|| -> Result<(), Box<dyn std::error::Error>> {
            let conn = self.conn.lock().unwrap();
            let rekey_query = format!("PRAGMA rekey = \"x'{}'\";", new_key_hex);
            conn.execute_batch(&rekey_query)?;
            conn.execute_batch("PRAGMA wal_checkpoint(FULL);")?;
            conn.query_row("SELECT count(*) FROM sse_events;", [], |_| Ok(()))?;
            Ok(())
        })();

        match rotation_result {
            Ok(_) => {
                crate::crypto::update_stored_db_key(new_key_hex)?;
                if let Some(parent_dir) = backup_path.parent() {
                    let _ = backup_retention::prune_old_backups(parent_dir, 3);
                }
                println!("[Database] Rekey validated. Retained backup as recovery point.");
                Ok(())
            }
            Err(err) => {
                eprintln!("[Database Error] Rekey failed: {err}. Restoring from backup...");
                let db_path = self.get_db_path()?;
                fs::copy(&backup_path, &db_path)?;
                Err(err)
            }
        }
    }

    pub fn get_last_rotation_timestamp(&self) -> Result<u64, rusqlite::Error> {
        let conn = self.conn.lock().unwrap();
        let val: String = conn.query_row(
            "SELECT value FROM db_metadata WHERE key = 'last_key_rotation_epoch';",
            [],
            |row| row.get(0),
        )?;

        Ok(val.parse::<u64>().unwrap_or(0))
    }

    pub fn update_last_rotation_timestamp(&self, epoch_secs: u64) -> Result<(), rusqlite::Error> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT INTO db_metadata (key, value) VALUES ('last_key_rotation_epoch', ?1)
             ON CONFLICT(key) DO UPDATE SET value = excluded.value;",
            params![epoch_secs.to_string()],
        )?;
        Ok(())
    }

    fn get_db_path(&self) -> Result<PathBuf, Box<dyn std::error::Error>> {
        let proj_dirs = ProjectDirs::from("com", "ActiveAssistant", "Daemon")
            .ok_or("Failed to determine application storage directory")?;
        Ok(proj_dirs.data_local_dir().join("events_encrypted.db"))
    }
}