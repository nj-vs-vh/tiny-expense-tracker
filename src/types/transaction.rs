use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Deserialize, Serialize)]
pub struct Transaction {
    id: String,
    timestamp: DateTime<Utc>,
    amount: f32,
    pool_id: String, // NOTE: this also determines the currency
    description: String,

    conversion_paired_transaction_id: Option<String>,

    // i.e. one transaction implying a number of small actual transactions too small to be tracked
    is_diffuse: bool,
}
