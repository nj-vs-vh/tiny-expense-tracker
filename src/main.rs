mod api_types;
mod api_utils;
mod storage;
mod types;

use api_types::PaginationParams;
use api_utils::to_http500;
use axum::extract::Query;
use tower_http::trace;
use tracing::Level;

use api_types::AppState;
use api_types::Auth;
use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use storage::Storage;
use types::money_pool::MoneyPool;

fn make_router() -> Router<()> {
    let state = AppState::new(storage::SharedInmemoryStorage::new());
    Router::new()
        .nest(
            "/api",
            Router::new().route("/pool", get(get_money_pools).post(add_money_pool)),
        )
        .with_state(state)
        .layer(
            trace::TraceLayer::new_for_http()
                .make_span_with(trace::DefaultMakeSpan::new().level(Level::INFO))
                .on_response(trace::DefaultOnResponse::new().level(Level::INFO)),
        )
}

async fn add_money_pool(
    Auth { user_id }: Auth,
    State(mut state): State<AppState>,
    Json(new_pool): Json<MoneyPool>,
) -> Result<(), (StatusCode, String)> {
    state
        .storage
        .add_pool(&user_id, new_pool)
        .await
        .map_err(to_http500)
}

#[axum_macros::debug_handler]
async fn get_money_pools(
    Auth { user_id }: Auth,
    State(state): State<AppState>,
) -> Result<Json<Vec<MoneyPool>>, (StatusCode, String)> {
    Ok(Json(
        state
            .storage
            .load_pools(&user_id)
            .await
            .map_err(to_http500)?,
    ))
}

#[tokio::main]
async fn main() {
    let format = tracing_subscriber::fmt::format()
        .with_level(true) // don't include levels in formatted output
        .with_target(true) // don't include targets
        .with_thread_ids(false) // include the thread ID of the current thread
        .with_thread_names(false) // include the name of the current thread
        .compact(); // use the `Compact` formatting style.
    tracing_subscriber::fmt().event_format(format).init();

    let listener = tokio::net::TcpListener::bind("127.0.0.1:3000")
        .await
        .unwrap();
    tracing::info!("listening on {}", listener.local_addr().unwrap());
    let router = make_router();
    axum::serve(listener, router).await.unwrap();
}
