use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::sse::{Event, KeepAlive, Sse},
};
use futures_util::StreamExt;
use serde::{Deserialize, Serialize};
use std::{convert::Infallible, sync::Arc, time::Duration};

use crate::observer::ContinuousObserver;

const OLLAMA_GENERATE_URL: &str = "http://127.0.0.1:11434/api/generate";
const MODEL_NAME: &str = "qwen2.5-coder:latest";

#[derive(Deserialize)]
pub struct FimQuery {
    pub prefix: Option<String>,
    pub suffix: Option<String>,
}

#[derive(Serialize)]
struct OllamaGenerateRequest<'a> {
    model: &'a str,
    prompt: String,
    stream: bool,
    options: OllamaOptions,
}

#[derive(Serialize)]
struct OllamaOptions {
    temperature: f32,
    stop: Vec<String>,
}

#[derive(Deserialize)]
struct OllamaChunk {
    response: String,
    done: bool,
}

pub async fn stream_fim_tokens(
    State(observer): State<Arc<ContinuousObserver>>,
    Query(query): Query<FimQuery>,
) -> Result<Sse<impl tokio_stream::Stream<Item = Result<Event, Infallible>>>, StatusCode> {
    let ctx = observer.current_context.read().await;
    let prefix = query.prefix.as_deref().unwrap_or(&ctx.file_prefix);
    let suffix = query.suffix.as_deref().unwrap_or(&ctx.file_suffix);

    let fim_prompt = format!(
        "<|fim_prefix|>// Context: {}\n{}<|fim_suffix|>\n{}<|fim_middle|>",
        ctx.active_window_title, prefix, suffix
    );

    let client = reqwest::Client::new();
    let payload = OllamaGenerateRequest {
        model: MODEL_NAME,
        prompt: fim_prompt,
        stream: true,
        options: OllamaOptions {
            temperature: 0.1,
            stop: vec![
                "<|file_sep|>".into(),
                "<|fim_prefix|>".into(),
                "<|fim_suffix|>".into(),
                "<|endoftext|>".into(),
            ],
        },
    };

    let upstream_res = client
        .post(OLLAMA_GENERATE_URL)
        .json(&payload)
        .send()
        .await
        .map_err(|_| StatusCode::BAD_GATEWAY)?;

    if !upstream_res.status().is_success() {
        return Err(StatusCode::BAD_GATEWAY);
    }

    let mut byte_stream = upstream_res.bytes_stream();

    let event_stream = async_stream::stream! {
        let mut buffer = String::new();

        while let Some(chunk_result) = byte_stream.next().await {
            match chunk_result {
                Ok(bytes) => {
                    if let Ok(text) = std::str::from_utf8(&bytes) {
                        buffer.push_str(text);

                        while let Some(newline_idx) = buffer.find('\n') {
                            let line = buffer[..newline_idx].trim().to_string();
                            buffer.drain(..=newline_idx);

                            if line.is_empty() {
                                continue;
                            }

                            if let Ok(chunk) = serde_json::from_str::<OllamaChunk>(&line) {
                                let sse_payload = serde_json::json!({
                                    "token": chunk.response,
                                    "done": chunk.done,
                                });

                                yield Ok(Event::default().event("fim_token").data(sse_payload.to_string()));

                                if chunk.done {
                                    return;
                                }
                            }
                        }
                    }
                }
                Err(_) => return,
            }
        }
    };

    Ok(Sse::new(event_stream).keep_alive(
        KeepAlive::new()
            .interval(Duration::from_secs(10))
            .text("ping"),
    ))
}