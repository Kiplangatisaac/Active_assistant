use std::sync::Arc;
use std::time::Duration;
use tokio::sync::RwLock;

#[derive(Default, Clone, serde::Serialize, serde::Deserialize)]
pub struct LiveContextSnapshot {
    pub active_window_title: String,
    pub ocr_screen_excerpt: String,
    pub active_file_path: Option<String>,
    pub file_prefix: String,
    pub file_suffix: String,
    pub cursor_line: usize,
    pub timestamp_ms: u64,
}

pub struct ContinuousObserver {
    pub current_context: Arc<RwLock<LiveContextSnapshot>>,
}

impl ContinuousObserver {
    pub fn new() -> Self {
        Self {
            current_context: Arc::new(RwLock::new(LiveContextSnapshot::default())),
        }
    }

    /// Runs non-stop on a 500ms ticker, tracking screen & editor changes
    pub fn start_autonomous_capture(&self) {
        let state = self.current_context.clone();

        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_millis(500));
            loop {
                interval.tick().await;

                let title = get_focused_window_title();
                if is_editor_window(&title) {
                    let snapshot = capture_active_editor_state(&title);
                    let mut lock = state.write().await;
                    *lock = snapshot;
                }
            }
        });
    }
}

fn get_focused_window_title() -> String {
    "Visual Studio Code - project/src/main.rs".to_string()
}

fn is_editor_window(title: &str) -> bool {
    title.contains("Visual Studio Code") || title.contains("Cursor") || title.contains("RustRover")
}

fn capture_active_editor_state(title: &str) -> LiveContextSnapshot {
    LiveContextSnapshot {
        active_window_title: title.to_string(),
        ocr_screen_excerpt: "".to_string(),
        active_file_path: Some("src/worker.rs".to_string()),
        file_prefix: "pub async fn process_job(job: Job) -> Result<(), Error> {\n    let id = job.id;\n    ".to_string(),
        file_suffix: "\n    save_status(id, Status::Done).await\n}".to_string(),
        cursor_line: 42,
        timestamp_ms: 1774300000000,
    }
}