use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Deserialize, Serialize, Clone)]
pub struct Transaction {
    pub id: String,
    pub timestamp: DateTime<Utc>,
    pub amount: f32,
    pub pool_id: String, // NOTE: this also determines the currency
    pub description: String,

    pub conversion_paired_transaction_id: Option<String>,

    // i.e. one transaction implying a number of small actual transactions too small to be tracked
    pub is_diffuse: bool,
}

impl Transaction {
    #[allow(dead_code)]
    pub fn new_regular(amount: f32, pool_id: String, description: String) -> Transaction {
        Transaction {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now(),
            amount,
            pool_id,
            description,
            conversion_paired_transaction_id: None,
            is_diffuse: false,
        }
    }
}

#[derive(Serialize, Deserialize, Debug, Default)]
pub struct TransactionFilter {
    min_timestamp: Option<DateTime<Utc>>,
    max_timestamp: Option<DateTime<Utc>>,
    pool_ids: Option<Vec<String>>,
}

impl TransactionFilter {
    pub fn matches(&self, t: &Transaction) -> bool {
        if let Some(min_dt) = self.min_timestamp {
            if t.timestamp < min_dt {
                return false;
            }
        }
        if let Some(max_dt) = self.max_timestamp {
            if t.timestamp > max_dt {
                return false;
            }
        }
        if let Some(pool_ids) = &self.pool_ids {
            if !pool_ids.contains(&t.pool_id) {
                return false;
            }
        }
        true
    }
}
