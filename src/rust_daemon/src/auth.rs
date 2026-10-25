use std::sync::Arc;
use std::time::{Duration, Instant};
use subtle::ConstantTimeEq;
use tokio::sync::RwLock;

pub struct TokenRecord {
    pub value: String,
    pub created_at: Instant,
    pub ttl: Duration,
}

pub struct ActiveAuthStore {
    pub current: TokenRecord,
    pub previous: Option<TokenRecord>,
}

#[derive(Clone)]
pub struct AuthState {
    store: Arc<RwLock<ActiveAuthStore>>,
    grace_period: Duration,
}

impl AuthState {
    pub fn new(ttl: Duration, grace_period: Duration) -> Self {
        let initial_token = Self::generate_token();
        Self {
            store: Arc::new(RwLock::new(ActiveAuthStore {
                current: TokenRecord {
                    value: initial_token,
                    created_at: Instant::now(),
                    ttl,
                },
                previous: None,
            })),
            grace_period,
        }
    }

    fn generate_token() -> String {
        let mut bytes = [0u8; 32];
        rand::thread_rng().fill_bytes(&mut bytes);
        hex::encode(bytes)
    }

    pub async fn verify_token_with_remaining(&self, candidate: &str) -> Option<Duration> {
        let store = self.store.read().await;

        if Self::constant_time_equals(&store.current.value, candidate) {
            let elapsed = store.current.created_at.elapsed();
            if elapsed < store.current.ttl {
                return Some(store.current.ttl - elapsed);
            }
        }

        if let Some(ref prev) = store.previous {
            if Self::constant_time_equals(&prev.value, candidate) {
                let elapsed = prev.created_at.elapsed();
                if elapsed < prev.ttl {
                    return Some(prev.ttl - elapsed);
                }
            }
        }

        None
    }

    pub async fn rotate_preemptive(&self) -> (String, Duration) {
        let mut store = self.store.write().await;
        let new_token = Self::generate_token();
        let default_ttl = store.current.ttl;

        store.previous = Some(TokenRecord {
            value: store.current.value.clone(),
            created_at: Instant::now(),
            ttl: self.grace_period,
        });

        store.current = TokenRecord {
            value: new_token.clone(),
            created_at: Instant::now(),
            ttl: default_ttl,
        };

        (new_token, default_ttl)
    }

    fn constant_time_equals(a: &str, b: &str) -> bool {
        let a_bytes = a.as_bytes();
        let b_bytes = b.as_bytes();
        if a_bytes.len() != b_bytes.len() {
            return false;
        }
        a_bytes.ct_eq(b_bytes).into()
    }
}