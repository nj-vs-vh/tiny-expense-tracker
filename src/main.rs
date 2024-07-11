mod http_utils;
mod storage;
mod types;

use tower_http::trace;
use tracing::Level;

use axum::{extract::State, http::StatusCode, routing::post, Json, Router};
use http_utils::AppState;
use http_utils::Auth;
use types::money_pool::MoneyPool;

#[tokio::main]
async fn main() {
    let format = tracing_subscriber::fmt::format()
        .with_level(true) // don't include levels in formatted output
        .with_target(true) // don't include targets
        .with_thread_ids(false) // include the thread ID of the current thread
        .with_thread_names(false) // include the name of the current thread
        .compact(); // use the `Compact` formatting style.
    tracing_subscriber::fmt().event_format(format).init();

    let state = AppState::new(storage::SharedInmemoryStorage::new());

    let app = Router::new()
        .nest("/api", Router::new().route("/pool", post(add_money_pool)))
        .with_state(state)
        .layer(
            trace::TraceLayer::new_for_http()
                .make_span_with(trace::DefaultMakeSpan::new().level(Level::INFO))
                .on_response(trace::DefaultOnResponse::new().level(Level::INFO)),
        );

    let listener = tokio::net::TcpListener::bind("127.0.0.1:3000")
        .await
        .unwrap();
    tracing::info!("listening on {}", listener.local_addr().unwrap());
    axum::serve(listener, app).await.unwrap();
}

async fn add_money_pool(
    Auth { user_id }: Auth,
    State(_state): State<AppState>,
    // Json(_pool): Json<MoneyPool>,
) -> Result<String, (StatusCode, String)> {
    // storage.add_pool(user_id, new_pool)
    // let mut conn = storage.get().await.map_err(to_http500)?;
    // let result: String = conn.get("foo").await.map_err(to_http500)?;
    Ok(user_id)
}
