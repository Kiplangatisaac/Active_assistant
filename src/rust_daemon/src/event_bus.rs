use crate::db::NotificationEvent;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::broadcast;

#[derive(Clone)]
pub struct PersistentEventBus {
    db: crate::db::EncryptedDatabaseStore,
    tx: broadcast::Sender<NotificationEvent>,
}

impl PersistentEventBus {
    pub fn new(db: crate::db::EncryptedDatabaseStore, channel_capacity: usize) -> Self {
        let (tx, _) = broadcast::channel(channel_capacity);
        Self { db, tx }
    }

    pub async fn dispatch(&self, event_type: String, action_key: String) -> Result<NotificationEvent, Box<dyn std::error::Error>> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_millis() as u64;

        let db = self.db.clone();
        let e_type = event_type.clone();
        let a_key = action_key.clone();

        let id = tokio::task::spawn_blocking(move || {
            db.insert_event(&e_type, &a_key, now)
        }).await??;

        let event = NotificationEvent {
            id,
            event_type,
            action_key,
            timestamp_ms: now,
        };

        let _ = self.tx.send(event.clone());
        Ok(event)
    }

    pub async fn get_missed_events(&self, last_id: u64) -> Result<Vec<NotificationEvent>, Box<dyn std::error::Error>> {
        let db = self.db.clone();
        let missed = tokio::task::spawn_blocking(move || {
            db.get_events_after(last_id)
        }).await??;

        Ok(missed)
    }

    pub fn subscribe(&self) -> broadcast::Receiver<NotificationEvent> {
        self.tx.subscribe()
    }
}