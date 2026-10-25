use notify_rust::{Hint, Notification, Timeout, Urgency};
use std::path::Path;

pub fn send_recovery_alert(snapshot_path: &Path) {
    let filename = snapshot_path
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("backup snapshot");

    let body_text = format!(
        "The encrypted database was corrupted and has been automatically restored from: {}",
        filename
    );

    std::thread::spawn(move || {
        let mut notif = Notification::new();
        notif
            .appname("Active Assistant")
            .summary("Database Auto-Recovery Triggered")
            .body(&body_text)
            .urgency(Urgency::Critical)
            .timeout(Timeout::Milliseconds(8000));

        #[cfg(not(target_os = "macos"))]
        {
            notif.hint(Hint::Category("dialog-warning".to_string()));
        }

        if let Err(e) = notif.show() {
            eprintln!("[Notification Error] Failed to show disaster-recovery alert: {e}");
        }
    });
}