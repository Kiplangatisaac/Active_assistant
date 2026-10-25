mod auth;
mod backup_retention;
mod corrupt_cleanup;
mod crypto;
mod db;
mod diagnostics;
mod event_bus;
mod fim_stream;
mod notifications;
mod observer;
mod recovery;
mod scheduler;

use auth::AuthState;
use axum::{
    extract::{Query, State},
    http::{header::HeaderMap, StatusCode},
    response::sse::{Event, KeepAlive, Sse},
    routing::{get, post},
    Json, Router,
};
use db::EncryptedDatabaseStore;
use event_bus::PersistentEventBus;
use observer::ContinuousObserver;
use serde::{Deserialize, Serialize};
use std::{convert::Infallible, sync::Arc, time::Duration};
use tokio_stream::{wrappers::BroadcastStream, StreamExt};

#[derive(Clone)]
pub struct AppState {
    pub auth: AuthState,
    pub bus: Arc<PersistentEventBus>,
    pub observer: Arc<ContinuousObserver>,
}

#[derive(Deserialize)]
pub struct AuthQuery {
    pub token: String,
    pub last_event_id: Option<u64>,
}

#[derive(Serialize)]
pub struct RefreshResponse {
    pub token: String,
    pub expires_in_seconds: u64,
}

pub async fn refresh_token_handler(
    State(state): State<AppState>,
    Query(params): Query<AuthQuery>,
) -> Result<Json<RefreshResponse>, StatusCode> {
    if state.auth.verify_token_with_remaining(&params.token).await.is_none() {
        return Err(StatusCode::UNAUTHORIZED);
    }

    let (new_token, ttl) = state.auth.rotate_preemptive().await;
    Ok(Json(RefreshResponse {
        token: new_token,
        expires_in_seconds: ttl.as_secs(),
    }))
}

pub async fn authenticated_sse_handler(
    State(state): State<AppState>,
    headers: HeaderMap,
    Query(params): Query<AuthQuery>,
) -> Result<Sse<impl Infallible tokio_stream::Stream<Item = Result<Event, Infallible>>>, StatusCode> {
    let remaining = match state.auth.verify_token_with_remaining(&query.token).await {
        Some(d) => d,
        None => return Err(StatusCode::UNAUTHORIZED),
    };

    let last_id = headers
        .get("last-event-id")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.parse::<u64>().ok())
        .or(query.last_event_id)
        .unwrap_or(0);

    let missed_events = state.bus.get_missed_events(last_id).await.map_err(|_| {
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let historical_stream = tokio_stream::iter(missed_events.into_iter().map(|evt| {
        let payload = serde_json::to_string(&evt).unwrap_or_default();
        Ok(Event::default()
            .id(evt.id.to_string())
            .event("notification_action")
            .data(payload))
    }));

    let rx = state.bus.subscribe();
    let live_stream = BroadcastStream::new(rx).filter_map(move |res| match res {
        Ok(evt) if evt.id > last_id => {
            let payload = serde_json::to_string(&evt).unwrap_or_default();
            Some(Ok(Event::default()
                .id(evt.id.to_string())
                .event("notification_action")
                .data(payload)))
        }
        _ => None,
    });

    let bounded = historical_stream.chain(live_stream).take_until(tokio::time::sleep(remaining));

    Ok(Sse::new(bounded).keep_alive(
        KeepAlive::new()
            .interval(Duration::from_secs(15))
            .text("ping"),
    ))
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let key = crypto::get_or_create_db_key()?;
    let outcome = EncryptedDatabaseStore::new(&key)?;
    let db_store = outcome.store;

    let bus = Arc::new(PersistentEventBus::new(db_store.clone(), 64));
    let observer = Arc::new(ContinuousObserver::new());
    observer.start_autonomous_capture();

    scheduler::start_maintenance_scheduler(db_store.clone());

    if let Some((snapshot_path, report)) = outcome.recovery_report {
        notifications::send_recovery_alert(&snapshot_path);
        let diagnostic_json = serde_json::to_string(&report)?;
        let _ = bus.dispatch("disaster_recovery_restored".to_string(), diagnostic_json).await;
    }

    let auth = AuthState::new(Duration::from_secs(300), Duration::from_secs(60));
    let state = AppState { auth, bus, observer: observer.clone() };

    let app = Router::new()
        .route("/events/sse", get(authenticated_sse_handler))
        .route("/auth/refresh", post(refresh_token_handler))
        .route("/events/fim", get(fim_stream::stream_fim_tokens))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("127.0.0.1:49215").await?;
    println!("[Daemon] Active loopback bridge bound to http://127.0.0.1:49215");

    axum::serve(listener, app).await?;
    Ok(())
}