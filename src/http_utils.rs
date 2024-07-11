use crate::storage;
use axum::async_trait;
use axum::{
    extract::{FromRef, FromRequestParts},
    http::{request::Parts, StatusCode},
    response::Response,
};

// can be adjusted to compile with various DB backend support
pub type AppStorage = storage::SharedInmemoryStorage;

#[derive(Clone)]
pub struct AppState {
    storage: AppStorage,
    // TODO: auth-related inmemory info storage here
}

impl AppState {
    pub fn new(storage: AppStorage) -> AppState {
        AppState { storage }
    }
}

pub fn to_http500<E>(err: E) -> (StatusCode, String)
where
    E: std::error::Error,
{
    (StatusCode::INTERNAL_SERVER_ERROR, err.to_string())
}

pub struct Auth {
    pub user_id: String,
}

#[async_trait]
impl<S> FromRequestParts<S> for Auth
where
    // keep `S` generic but require that it can produce a `MyLibraryState`
    // this means users will have to implement `FromRef<UserState> for MyLibraryState`
    AppState: FromRef<S>,
    S: Send + Sync,
{
    type Rejection = Response;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let state = AppState::from_ref(state);
        // TODO: either extract auth from trusted client with asymm. cryptography or lookup access token in app state
        return Ok(Auth {
            user_id: "temp".to_owned(),
        });
    }
}
